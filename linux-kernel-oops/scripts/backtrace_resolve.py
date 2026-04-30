#!/usr/bin/env python3
"""
backtrace_resolve.py — Batch backtrace resolution for kernel oops analysis.

For each backtrace entry this script:
  - Computes the symbol address via nm and cross-checks against any provided address
  - Applies the return-address -1 correction for all frames except index 0
  - Resolves file:line (including inlined frames) via addr2line -i
  - Extracts the complete function source from the git tree
  - Collects git blame commit hashes for the function
  - Lists recent commits that touched the function lines (git log -L)
  - For index 0 only: produces a disassembly window (15 insns before, 5 after crash)

vmlinux entries are resolved against the provided vmlinux file.
Module entries are resolved against the module's debug ELF, found by searching
modules_dir (if provided) for <module>.ko.debug then <module>.ko.

Input JSON schema:
  {
    "vmlinux":     "/path/to/vmlinux",
    "sourcedir":   "/path/to/linux-source-tree",
    "modules_dir": "/path/to/modules/root",   // optional; enables module resolution
    "entries": [
      {
        "index":    0,
        "function": "some_function",
        "offset":   "0x1a",          // hex string
        "size":     "0x2c",          // hex string, optional
        "module":   "vmlinux",       // "vmlinux" or loaded module name (e.g. "gfs2")
        "address":  "ffffffff81234567"  // optional; used for cross-check only
      }, ...
    ]
  }

Output fields (per entry):
  address_computed   — hex string: nm_base + offset
  address_formatted  — human-readable: "0x... (0x... + 0x...)" for the backtrace table
  source             — {primary: {function, file, line}, inlined_frames: [...]}
  function_source    — {file, start_line, end_line, code}
  git_blame_hashes   — list of unique commit hashes covering the function lines
  blame_details      — list of {hash, subject, fixes_tag?, cc_stable?, link?} (first 2 normal entries)
  fix_candidates     — list of {hash, subject, fixes_hash} commits that Fixes: any blame hash
                        (first 2 normal entries; searched in parallel across blame hashes)
  function_type      — "reporting" | "assert" | "normal"
                        reporting: exists only to emit the crash message; source/blame skipped
                        assert: precondition checker (canary); source shown but blame skipped
  recent_commits     — list of {hash, subject} from git log -L
  disasm             — disasm window string (index 0 only), with <<< crash marker
  skipped            — set (instead of above fields) when resolution was not possible
  note               — set when addr2line returned line 0 or heuristic misfired

Usage:
  python3 backtrace_resolve.py [--timing] [--sequential] input.json [output.json]
  If output.json is omitted, JSON is written to stdout.
  --timing      print per-call subprocess timing and a summary to stderr.
  --sequential  resolve entries one at a time (default is parallel).
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# ---------------------------------------------------------------------------
# Timing state (activated by --timing flag)
# ---------------------------------------------------------------------------

_TIMING   = False
_PARALLEL = False

# Aggregated timing: cmd_name -> [elapsed, ...]  (protected by _timing_lock)
_timing_data = defaultdict(list)
_timing_lock = threading.Lock()

# Lock for lazy module nm-table population in parallel mode
_module_cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Backtrace entry classification
# ---------------------------------------------------------------------------

# Functions that exist solely to emit the crash report.  They appear at the
# top of the stack but are not part of the bug; source extraction, disasm,
# and blame are all skipped for these.
REPORTING_FUNCTIONS = frozenset({
    "__dump_stack",
    "dump_stack",
    "dump_stack_lvl",
    "show_regs",
    "show_stack",
    "print_address_description",
    "kasan_report",
    "kasan_report_invalid_free",
    "kasan_report_access",
    "__kasan_report",
    "kasan_bug_type_str",
    "ubsan_epilogue",
    "ubsan_handle_type_mismatch_v1",
    "print_unlock_imbalance_bug",
})

# Functions that detect a violated precondition (canaries / assertions).
# They appear in the call chain and their source is shown, but they are NOT
# the root cause — the caller that violated the precondition is.  Blame and
# fix_candidates are skipped for these.
ASSERT_FUNCTIONS = frozenset({
    "might_sleep",
    "__might_sleep",
    "might_resched",
    "__might_resched",
    "cant_sleep",
    "cant_migrate",
})


def _timing_label(cmd):
    """Short human-readable label for a command list."""
    name = Path(cmd[0]).name   # nm, addr2line, git, objdump, …
    if name == "git" and len(cmd) > 1:
        return f"git-{cmd[1]}"   # git-blame, git-log
    return name


def _print_timing_summary():
    if not _timing_data:
        return
    print("\n  [timing summary]", file=sys.stderr)
    grand = 0.0
    for label in sorted(_timing_data):
        times  = _timing_data[label]
        total  = sum(times)
        grand += total
        avg    = total / len(times)
        print(f"    {label:20s}  calls={len(times):3d}  "
              f"total={total:7.3f}s  avg={avg:6.3f}s", file=sys.stderr)
    print(f"    {'TOTAL':20s}  {'':10}  total={grand:7.3f}s", file=sys.stderr)


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def run(cmd, cwd=None):
    """Run a command; return (stdout, stderr, returncode)."""
    if _TIMING:
        t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if _TIMING:
        elapsed = time.perf_counter() - t0
        with _timing_lock:
            _timing_data[_timing_label(cmd)].append(elapsed)
    return result.stdout, result.stderr, result.returncode


# ---------------------------------------------------------------------------
# nm: build symbol table once per ELF
# ---------------------------------------------------------------------------

def build_nm_table(elf_path, label=None):
    """
    Return a dict mapping function_name -> (base_addr_int, size_int|None).
    Uses `nm -S` (with size field).  Covers T/t/W/w (text) symbols.
    """
    tag = label or Path(elf_path).name
    print(f"  [nm] Building symbol table from {tag} (may take a moment)…",
          file=sys.stderr)
    stdout, _, rc = run(["nm", "-S", "--defined-only", elf_path])
    if rc != 0:
        return {}

    table = {}
    for line in stdout.splitlines():
        parts = line.split()
        # With -S: addr size type name   (4 fields)
        # Without size:  addr type name  (3 fields)
        if len(parts) == 4:
            addr_s, size_s, typ, name = parts
        elif len(parts) == 3:
            addr_s, typ, name = parts
            size_s = None
        else:
            continue
        if typ not in ("T", "t", "W", "w"):
            continue
        try:
            addr = int(addr_s, 16)
            size = int(size_s, 16) if size_s else None
        except ValueError:
            continue
        # Keep first occurrence (handles aliased symbols)
        if name not in table:
            table[name] = (addr, size)

    print(f"  [nm] {len(table)} text symbols loaded.", file=sys.stderr)
    return table


# ---------------------------------------------------------------------------
# Module ELF locator
# ---------------------------------------------------------------------------

def find_module_elf(modules_dir, module_name):
    """
    Search modules_dir recursively for a debug ELF for the named module.

    Kernel module names use '_' internally but filenames on disk may use
    either '_' or '-' (they are interchangeable in the module subsystem).
    Search order: <name>.ko.debug first (split debug info), then <name>.ko.

    Returns the path string of the first match, or None.
    """
    base = Path(modules_dir)
    # Build candidate name variants: original, _→- swap, -→_ swap
    variants = {module_name,
                module_name.replace("_", "-"),
                module_name.replace("-", "_")}
    for suffix in (".ko.debug", ".ko"):
        for variant in sorted(variants):  # deterministic order
            for found in base.rglob(f"{variant}{suffix}"):
                return str(found)
    return None


# ---------------------------------------------------------------------------
# addr2line with inlined frame support
# ---------------------------------------------------------------------------

def addr2line_lookup(vmlinux, address_int):
    """
    Return a list of frame dicts for address_int, innermost first.
    Each dict: {function, file, line}.
    Uses addr2line -i (inlined frames) -f (function names).
    """
    stdout, _, rc = run(
        ["addr2line", "-i", "-f", "-e", vmlinux, hex(address_int)]
    )
    if rc != 0 or not stdout.strip():
        return []

    frames = []
    lines = stdout.strip().splitlines()
    # Output alternates: function_name / file:line
    i = 0
    while i + 1 < len(lines):
        func = lines[i].strip()
        loc  = lines[i + 1].strip()
        if ":" in loc:
            file_part, _, line_part = loc.rpartition(":")
            try:
                lineno = int(line_part)
            except ValueError:
                lineno = 0
        else:
            file_part, lineno = loc, 0
        frames.append({"function": func, "file": file_part, "line": lineno})
        i += 2

    return frames


# ---------------------------------------------------------------------------
# Path normalization: strip distro build prefixes
# ---------------------------------------------------------------------------

def normalize_source_path(sourcedir, filepath):
    """
    Distro vmlinux files often embed build-directory paths such as
    'debian/build/build_amd64_none_amd64/kernel/rcu/tree.c' instead of
    the mainline 'kernel/rcu/tree.c'.

    Try the path as-is first.  If not found, progressively strip leading
    path components until the file is found in sourcedir, or give up.
    Returns the resolved relative path string, or None.
    """
    p = Path(filepath)
    parts = p.parts
    for start in range(len(parts)):
        candidate = Path(*parts[start:])
        if (Path(sourcedir) / candidate).exists():
            return str(candidate)
    return None


# ---------------------------------------------------------------------------
# Source file: extract the complete function containing target_line
# ---------------------------------------------------------------------------

def extract_function_source(sourcedir, filepath, target_line):
    """
    Extract the complete function that contains target_line.

    Strategy (matches the design in nextidea2.md):
      1. Scan *forward* from target_line for a closing '}' at column 0
         → end_line
      2. Scan *backward* from target_line for an opening '{' in a line
         that has no leading whitespace (function-level brace)
         → open_line
      3. Continue backward up to 10 more lines (or until the previous
         closing '}') to capture the signature + any doc comment
         → start_line

    Returns (start_line, end_line, code_str) with 1-based line numbers,
    or None on failure.
    """
    full_path = Path(sourcedir) / filepath
    if not full_path.exists():
        return None

    try:
        with open(full_path, "r", errors="replace") as fh:
            raw = fh.readlines()
    except OSError:
        return None

    n = len(raw)
    tgt = target_line - 1  # 0-based

    # --- Step 1: scan forward for closing '}' at column 0 ---
    end_idx = None
    for i in range(tgt, n):
        s = raw[i].rstrip("\n")
        # Accept bare '}', '};' (end of struct/union that wraps a func),
        # or '}' followed only by a comment
        if re.match(r"^\}\s*(;|/[/*].*)?$", s):
            end_idx = i
            break
    if end_idx is None:
        end_idx = min(tgt + 60, n - 1)  # fallback

    # --- Step 2: scan backward for opening '{' at column 0 ---
    open_idx = None
    for i in range(tgt, -1, -1):
        s = raw[i].rstrip("\n")
        # A line with no leading whitespace that contains '{'
        # (and is not a preprocessor directive)
        if s and not s[0] in (" ", "\t", "#", "/", "*") and "{" in s:
            open_idx = i
            break
    if open_idx is None:
        open_idx = max(0, tgt - 30)

    # --- Step 3: scan backward from open_idx for signature + comments ---
    sig_start = max(0, open_idx - 10)
    for i in range(open_idx - 1, max(open_idx - 10, -1), -1):
        s = raw[i].rstrip("\n")
        # Stop at a previous function's closing brace
        if re.match(r"^\}\s*(;|/[/*].*)?$", s):
            sig_start = i + 1
            break

    start_idx = sig_start
    # Expand tabs to 8 spaces (kernel coding style) so the analyst receives
    # clean, space-indented code from JSON without raw \t characters that
    # LLMs tend to drop or mishandle. The fact-checker will restore verbatim
    # tab indentation from the git tree in its cosmetic-fix pass.
    code = "".join(line.expandtabs(8) for line in raw[start_idx : end_idx + 1])
    # Sanity cap: if the extracted block is unreasonably large (>150 lines),
    # the heuristic likely misfired (e.g. macro-generated stubs in headers).
    # Return None so the caller notes the failure rather than dumping noise.
    if end_idx - start_idx + 1 > 150:
        return None
    return start_idx + 1, end_idx + 1, code  # 1-based


# ---------------------------------------------------------------------------
# git blame: collect commit hashes for a line range
# ---------------------------------------------------------------------------

def git_blame_hashes(sourcedir, filepath, start_line, end_line):
    """
    Return a deduplicated sorted list of commit hashes responsible for
    lines [start_line, end_line] in filepath (git blame --porcelain).
    """
    stdout, _, rc = run(
        ["git", "blame", "--porcelain",
         f"-L{start_line},{end_line}", "--", filepath],
        cwd=sourcedir,
    )
    if rc != 0:
        return []
    hashes = set()
    for line in stdout.splitlines():
        if re.match(r"^[0-9a-f]{40}\b", line):
            hashes.add(line[:40])
    return sorted(hashes)


# ---------------------------------------------------------------------------
# git log -L: recent commits touching the function
# ---------------------------------------------------------------------------

def git_log_function(sourcedir, filepath, start_line, end_line,
                     max_commits=10):
    """
    Return list of {hash, subject} for recent commits that modified
    lines [start_line, end_line] of filepath.
    """
    stdout, _, rc = run(
        ["git", "log", f"--max-count={max_commits}", "--oneline",
         f"-L{start_line},{end_line}:{filepath}"],
        cwd=sourcedir,
    )
    if rc != 0:
        return []
    commits = []
    for line in stdout.splitlines():
        m = re.match(r"^([0-9a-f]{7,40})\s+(.+)$", line)
        if m:
            commits.append({"hash": m.group(1), "subject": m.group(2)})
    return commits


# ---------------------------------------------------------------------------
# git commit metadata + Fixes: search (indices 0–1 only)
# ---------------------------------------------------------------------------

def git_commit_trailers(sourcedir, hashes):
    """
    Fetch subject and Fixes:/Cc: stable/Link: trailers for a list of commit
    hashes in a single git call.
    Returns dict: {full_hash: {hash, subject, fixes_tag?, cc_stable?, link?}}
    """
    if not hashes:
        return {}
    SEP = "==END_COMMIT=="
    stdout, _, rc = run(
        ["git", "log", "--no-walk", f"--format=%H%n%s%n%b%n{SEP}"] + list(hashes),
        cwd=sourcedir,
    )
    if rc != 0:
        return {}

    result = {}
    for block in stdout.split(SEP):
        lines = [l for l in block.split("\n") if l.strip()]
        if len(lines) < 2:
            continue
        full_hash = lines[0].strip()
        if not re.match(r"^[0-9a-f]{40}$", full_hash):
            continue
        subject    = lines[1].strip()
        body_lines = lines[2:]

        fixes_tag = None
        cc_stable = False
        link      = None
        for bl in body_lines:
            if re.match(r"Fixes:\s", bl, re.I):
                m = re.search(r"([0-9a-f]{7,40})", bl)
                if m:
                    fixes_tag = m.group(1)
            elif re.match(r"Cc:.*stable", bl, re.I):
                cc_stable = True
            elif re.match(r"Link:\s", bl, re.I):
                link = bl.split(":", 1)[1].strip()

        info = {"hash": full_hash, "subject": subject}
        if fixes_tag:
            info["fixes_tag"] = fixes_tag
        if cc_stable:
            info["cc_stable"] = True
        if link:
            info["link"] = link
        result[full_hash] = info
    return result


def git_find_fix_commits(sourcedir, hashes):
    """
    For each hash in hashes, search all branches for commits whose message
    contains 'Fixes: <hash>'.  Searches are run in parallel (one thread per
    hash) since each is an independent git-log call.
    Returns list of {hash, subject, fixes_hash}, deduplicated.
    """
    if not hashes:
        return []

    def search_one(h):
        short = h[:12]
        stdout, _, rc = run(
            ["git", "log", "--branches", "--remotes", "--oneline", "-E",
             "--since=3 years ago",
             "--grep", f"Fixes:.*{short}"],
            cwd=sourcedir,
        )
        hits = []
        if rc == 0:
            for line in stdout.splitlines():
                m = re.match(r"^([0-9a-f]{7,40})\s+(.+)$", line.strip())
                if m:
                    hits.append({"hash": m.group(1), "subject": m.group(2),
                                 "fixes_hash": h})
        return hits

    found = {}
    with ThreadPoolExecutor(max_workers=min(len(hashes), 10)) as pool:
        futures = {pool.submit(search_one, h): h for h in hashes}
        for fut in as_completed(futures):
            for item in fut.result():
                if item["hash"] not in found:
                    found[item["hash"]] = item

    # Drop fix candidates that reference a foundational commit — defined as
    # any blame hash that attracted more than 5 *distinct fix subjects*.
    # Stable backports of the same fix produce multiple commit hashes but
    # identical subjects, so we count unique subjects, not unique hashes.
    # A typical bug-introducing commit attracts 1–3 distinct fixes; a
    # foundational subsystem commit attracts 10+.
    from collections import defaultdict as _dd
    subj_sets = _dd(set)
    for item in found.values():
        subj_sets[item["fixes_hash"]].add(item["subject"])
    return [item for item in found.values()
            if len(subj_sets[item["fixes_hash"]]) <= 5]



def _companion_ko(debug_elf):
    """
    Given a path to a split-debug .ko.debug file, return the path to the
    companion .ko file that holds the actual code (NOBITS → real bytes).

    Fedora/RHEL layout:
      .ko.debug  …/usr/lib/debug/lib/modules/<uname>/kernel/…/<mod>.ko.debug
      .ko        …/lib/modules/<uname>/kernel/…/<mod>.ko
    """
    p = str(debug_elf)
    if not p.endswith(".ko.debug"):
        return None
    companion = p.replace("/usr/lib/debug/lib/modules/", "/lib/modules/", 1)[:-len(".debug")]
    return companion if Path(companion).exists() else None


def disassemble_window(elf, func_addr, func_size, crash_offset,
                       before=15, after=5):
    """
    Disassemble the function containing the crash and return a window of
    `before` instructions before and `after` instructions after the crash
    instruction, with a '<<< crash' marker on the crash line.
    Returns a string, or None on failure.

    For split-debug .ko.debug files (which carry NOBITS .text sections),
    the companion .ko is tried automatically for the actual code bytes.
    """
    if func_addr is None:
        return None

    # Split-debug .ko.debug files have NOBITS .text — no bytes to disassemble.
    # Fall back to the companion .ko (same path under /lib/modules/).
    disasm_elf = elf
    if str(elf).endswith(".ko.debug"):
        companion = _companion_ko(elf)
        if companion:
            disasm_elf = companion
        else:
            return None   # no companion available; skip silently

    stop_addr = func_addr + (func_size or 0x1000)
    stdout, _, rc = run([
        "objdump", "-d", "--no-show-raw-insn",
        f"--start-address={hex(func_addr)}",
        f"--stop-address={hex(stop_addr)}",
        disasm_elf,
    ])
    if rc != 0 or not stdout.strip():
        return None

    crash_addr = func_addr + crash_offset

    # Parse instruction lines: "address:  mnemonic operands"
    insn_lines = []
    for line in stdout.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+(.+)", line)
        if m:
            insn_lines.append((int(m.group(1), 16), line))

    if not insn_lines:
        return None   # objdump ran but produced no instructions

    # Find index of the crash instruction (last insn with addr <= crash_addr)
    crash_idx = 0
    for i, (addr, _) in enumerate(insn_lines):
        if addr <= crash_addr:
            crash_idx = i

    start_i = max(0, crash_idx - before)
    end_i   = min(len(insn_lines) - 1, crash_idx + after)

    out = []
    for i in range(start_i, end_i + 1):
        addr, text = insn_lines[i]
        marker = "   <<< crash" if i == crash_idx else ""
        out.append(text + marker)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Address parsing helper
# ---------------------------------------------------------------------------

def parse_addr(s):
    """Parse a hex address string with or without '0x' prefix."""
    if s is None:
        return None
    s = s.strip()
    try:
        return int(s, 16)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Per-entry resolver
# ---------------------------------------------------------------------------

def resolve_entry(entry, vmlinux, sourcedir, nm_table, modules_dir, module_nm_cache):
    """
    Resolve one backtrace entry.

    vmlinux/nm_table     — the core kernel ELF and its pre-built nm table.
    modules_dir          — root directory to search for module debug ELFs
                           (None disables module resolution).
    module_nm_cache      — dict {elf_path: nm_table}, populated lazily.
    """
    idx           = entry["index"]
    function      = entry["function"]
    module        = entry.get("module", "vmlinux")
    offset        = parse_addr(entry.get("offset", "0x0")) or 0
    function_type = entry.get("_function_type", "normal")
    generate_blame = entry.get("_generate_blame", False)

    result = {"index": idx, "function": function, "module": module,
              "function_type": function_type}

    # Reporting functions exist only to emit the crash message.
    # Skip all expensive resolution — they are not crash sites.
    if function_type == "reporting":
        return result

    # --- Select debug ELF and nm table ---
    if module == "vmlinux":
        debug_elf  = vmlinux
        entry_nm   = nm_table
    else:
        # Module entry: locate the debug ELF and build (or retrieve) its nm table
        if not modules_dir:
            result["skipped"] = (
                "module entry — provide 'modules_dir' in input JSON to enable resolution"
            )
            return result
        module_elf = find_module_elf(modules_dir, module)
        if not module_elf:
            result["skipped"] = f"module ELF not found under modules_dir for '{module}'"
            return result
        result["module_elf"] = module_elf
        # Lock protects lazy population; build_nm_table is expensive so check twice
        if module_elf not in module_nm_cache:
            with _module_cache_lock:
                if module_elf not in module_nm_cache:
                    module_nm_cache[module_elf] = build_nm_table(module_elf, label=module)
        debug_elf = module_elf
        entry_nm  = module_nm_cache[module_elf]

    # --- Address: compute from nm, cross-check against provided ---
    nm_base, nm_size = entry_nm.get(function, (None, None))
    computed_addr    = (nm_base + offset) if nm_base is not None else None
    provided_addr    = parse_addr(entry.get("address"))

    if computed_addr is not None:
        result["address_computed"]   = hex(computed_addr)
        result["address_formatted"]  = f"{hex(computed_addr)} ({hex(nm_base)} + {hex(offset)})"
    if provided_addr is not None:
        result["address_provided"] = hex(provided_addr)
        if computed_addr is not None:
            result["address_match"] = (computed_addr == provided_addr)

    # Effective address for addr2line: prefer computed, fall back to provided
    effective = computed_addr if computed_addr is not None else provided_addr
    if effective is None:
        result["error"] = "could not determine address (symbol not in nm output and no address provided)"
        return result

    # Apply return-address -1 correction for all frames except index 0
    if idx != 0:
        a2l_addr = effective - 1
        result["addr2line_correction"] = "-1 (return address)"
    else:
        a2l_addr = effective

    result["addr2line_address"] = hex(a2l_addr)

    # --- addr2line with inlined frames ---
    frames = addr2line_lookup(debug_elf, a2l_addr)
    if frames:
        primary = frames[0]
        primary_file = primary.get("file", "")
        primary_line = primary.get("line", 0)
        # Normalize build path → real source path and store it in the result
        resolved_file = normalize_source_path(sourcedir, primary_file) if primary_file and not primary_file.startswith("?") else None
        if resolved_file:
            primary["file"] = resolved_file
        # Normalize inlined frame paths too
        for frame in frames[1:]:
            fp = frame.get("file", "")
            if fp and not fp.startswith("?"):
                nfp = normalize_source_path(sourcedir, fp)
                if nfp:
                    frame["file"] = nfp
        result["source"] = {
            "primary":        primary,
            "inlined_frames": frames[1:],
        }
        # Use resolved path for downstream lookups
        if resolved_file:
            primary_file = resolved_file
    else:
        result["source"] = None
        primary_file    = ""
        resolved_file   = None
        primary_line    = 0

    # --- Function source extraction ---
    # resolved_file is already set above (normalized from DWARF build path)
    if resolved_file and primary_line > 0:
        func_src = extract_function_source(sourcedir, resolved_file, primary_line)
        if func_src:
            start_line, end_line, code = func_src
            result["function_source"] = {
                "file":       resolved_file,
                "start_line": start_line,
                "end_line":   end_line,
                "code":       code,
            }

            # git blame hashes
            blame_hashes = git_blame_hashes(
                sourcedir, resolved_file, start_line, end_line
            )
            result["git_blame_hashes"] = blame_hashes

            # Enrich blame hashes with commit metadata and search for
            # follow-up Fixes: commits — but only for entries designated
            # as blame targets (first 2 "normal" entries, pre-classified
            # in main()).  Assert/reporting entries are excluded.
            if generate_blame and blame_hashes:
                trailers = git_commit_trailers(sourcedir, blame_hashes)
                if trailers:
                    result["blame_details"] = list(trailers.values())
                fix_cands = git_find_fix_commits(sourcedir, blame_hashes)
                if fix_cands:
                    result["fix_candidates"] = fix_cands

            # Recent commits touching these lines
            result["recent_commits"] = git_log_function(
                sourcedir, resolved_file, start_line, end_line
            )
        else:
            result["function_source"] = None
            result["note"] = f"function boundary heuristic misfired (extracted >150 lines) for {resolved_file}:{primary_line}"
    elif primary_file and not primary_file.startswith("?"):
        result["function_source"] = None
        build_path = primary_file if not resolved_file else resolved_file
        if primary_line == 0:
            result["note"] = f"addr2line returned line 0 for {build_path} — DWARF may be incomplete at this address"
        else:
            result["note"] = f"source file not found in sourcedir: {primary_file}"

    # --- Disassembly window for index 0 ---
    if idx == 0:
        result["disasm"] = disassemble_window(
            debug_elf, nm_base, nm_size, offset
        )
        if result["disasm"] is None and str(debug_elf).endswith(".ko.debug"):
            companion = _companion_ko(debug_elf)
            if companion:
                result["disasm_note"] = (
                    f"disassembly sourced from companion {companion}"
                )
            else:
                result["disasm_note"] = (
                    "split-debug .ko.debug has NOBITS .text — "
                    "no companion .ko found; install the kernel-modules "
                    "package to obtain disassembly"
                )

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _TIMING, _PARALLEL

    # Strip flag args before positional arg parsing
    flags = {"--timing", "--sequential"}
    args  = [a for a in sys.argv[1:] if a not in flags]
    seen  = set(sys.argv[1:]) & flags
    _TIMING   = "--timing"     in seen
    _PARALLEL = "--sequential" not in seen   # parallel is the default

    if len(args) < 1:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    input_path  = args[0]
    output_path = args[1] if len(args) >= 2 else None

    with open(input_path) as fh:
        data = json.load(fh)

    vmlinux     = data["vmlinux"]
    sourcedir   = data["sourcedir"]
    modules_dir = data.get("modules_dir")        # optional
    entries     = data["entries"]

    if not Path(vmlinux).exists():
        print(f"Error: vmlinux not found: {vmlinux}", file=sys.stderr)
        sys.exit(1)
    if not Path(sourcedir).exists():
        print(f"Error: sourcedir not found: {sourcedir}", file=sys.stderr)
        sys.exit(1)
    if modules_dir and not Path(modules_dir).exists():
        print(f"Warning: modules_dir not found: {modules_dir} — module entries will be skipped",
              file=sys.stderr)
        modules_dir = None

    nm_table        = build_nm_table(vmlinux, label="vmlinux")
    module_nm_cache = {}   # elf_path -> nm_table, populated lazily (lock-protected)

    # Pre-classify entries and mark the first 2 non-reporting, non-assert
    # entries as blame targets (replacing the old idx <= 1 heuristic).
    normal_blame_count = 0
    for e in entries:
        fn = e["function"]
        # Strip compiler-generated suffixes (.part.N, .constprop.N, .cold,
        # .isra.N, .llvm.N) before set lookups so that e.g.
        # "print_unlock_imbalance_bug.cold" is still classified as reporting.
        # The original fn value is kept in the entry for all other purposes
        # (reporting, assembly, address resolution).
        fn_base = re.sub(r'\.(part|constprop|isra|cold|llvm)\.[0-9]+$|\.cold$', '', fn)
        if fn_base in REPORTING_FUNCTIONS:
            e["_function_type"] = "reporting"
        elif fn_base in ASSERT_FUNCTIONS:
            e["_function_type"] = "assert"
        else:
            e["_function_type"] = "normal"
            if normal_blame_count < 2:
                e["_generate_blame"] = True
                normal_blame_count += 1

    def _resolve(entry):
        mod = entry.get("module", "vmlinux")
        print(
            f"  Resolving [{entry['index']}] {entry['function']}+{entry.get('offset','?')}"
            f"{' [' + mod + ']' if mod != 'vmlinux' else ''} …",
            file=sys.stderr,
        )
        return resolve_entry(entry, vmlinux, sourcedir, nm_table,
                             modules_dir, module_nm_cache)

    if _PARALLEL:
        # One thread per entry; results re-sorted by index to preserve order
        with ThreadPoolExecutor(max_workers=min(len(entries), 10)) as pool:
            futures = {pool.submit(_resolve, e): e["index"] for e in entries}
            resolved = {idx: f.result() for f, idx in
                        ((f, futures[f]) for f in as_completed(futures))}
        results = [resolved[e["index"]] for e in entries]
    else:
        results = [_resolve(e) for e in entries]

    output = {"results": results}

    if output_path:
        with open(output_path, "w") as fh:
            json.dump(output, fh, indent=2)
        print(f"Output written to {output_path}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2))

    if _TIMING:
        _print_timing_summary()


if __name__ == "__main__":
    main()
