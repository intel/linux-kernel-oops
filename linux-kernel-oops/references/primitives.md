# Basic Primitives - Data Extraction

This file contains the detailed procedures for extracting structured data from a Linux Kernel OOPS report.

## Table of Contents
1. [Classify the crash type](#classify-the-crash-type)
2. [General fundamentals extraction](fundamentals.md) *(demand-load — kernel version, process, modules, taint flags, hardware, email MSGID)*
3. [Backtrace extraction](backtrace.md) *(demand-load)*
4. [Locks held extraction](lockdep.md) *(demand-load — only when "N locks held" block is present)*
5. [Code byte line extraction](#code-byte-line-extraction)
5. [CPU Registers](#cpu-registers)
6. [Linux distribution specific tasks](#linux-distribution-specific-tasks) *(Debian, Fedora, Ubuntu)*
7. [General source tree fallback](#general-source-tree-fallback) *(oops-workdir/linux for unknown distros or fallback)*
8. [Locating the vmlinux file](#locating-the-vmlinux-file)
9. [Locating a kernel module](#locating-a-kernel-module)
10. [Mapping backtrace lines to code](mapping.md) *(demand-load)*
11. [Reporting a source code function](reporting.md) *(demand-load)*
12. [Generating HTML output](#generating-html-output)
13. [Fetching an OOPS from a bug tracker](bugtracker.md) *(demand-load — Launchpad, kernel Bugzilla, Debian BTS, Red Hat Bugzilla)*
14. [Transcribing an OOPS from a screenshot or image](image.md) *(demand-load — marker_single preferred; vision model fallback)*
15. [Structured archive](#structured-archive) *(default report output location with source-based directory layout)*
16. [Preparing a patch email](patch.md) *(demand-load when a new fix patch was produced)*
17. [semcode MCP navigation](semcode.md) *(demand-load when semcode MCP is available — fast kernel code search, call graph traversal, lore search)*

---

## Classify the crash type
Identify the primary signature of the crash:
- **Oops**: General kernel crash (e.g., `BUG: unable to handle kernel paging request`).
- **Panic**: Fatal error where the kernel cannot continue (e.g., `Kernel panic - not syncing`).
- **BUG**: Hit a `BUG()` or `BUG_ON()` macro.
- **WARNING**: Hit a `WARN()` or `WARN_ON()` macro.

## General fundamentals extraction

**Demand-load: read [fundamentals.md](fundamentals.md) now** when starting this step.
That file covers timestamps, the Key Elements table, UNAME/distro detection,
git-describe versions, crashing process, module list, taint flags, hardware name,
and email MSGID extraction.

## Backtrace extraction

**Demand-load: read [backtrace.md](backtrace.md) now** when starting this step.
That file covers the Backtrace table format, RIP as first entry, Format 1/2,
IRQ/Task context markers, module data, build ID hashes, and "?" marker handling.


## Code byte line extraction
The `Code:` line shows the machine code around the failing instruction.
- The byte surrounded by `< >` is the instruction at the instruction pointer (`RIP`).
- Example: `Code: 48 89 45 f0 48 8b 45 f0 <48> 8b 00`.

**Tip:** You can use the `scripts/decodecode` utility from the kernel source tree to disassemble this line. If a kernel source tree is not available, ensure you have a local copy of this script to aid in analysis.

**When the kernel cannot read the code bytes:** If the `Code:` line reads
```
Code: Unable to access opcode bytes at <address>.
```
this means the instruction pointer was pointing to unmapped memory at the time
of the crash. No disassembly is possible. Record this in the report as-is and
treat it as corroborating evidence: an unmapped RIP is consistent with a NULL
or invalid function pointer dereference, and aligns with `RIP: 0010:0x0` or
any other non-canonical address in the RIP field.

## CPU Registers
Extract the register dump (RAX, RBX, RCX, RDX, RSI, RDI, RBP, R8-R15, RIP, RSP).
- For paging requests, check `CR2` (the address that caused the fault).
- **Analysis Tips:** 
    - Compare `RIP` with the backtrace to confirm the crash location.
    - Check if `RSP` (Stack Pointer) looks reasonable for a kernel stack (typically starts with `ffff...`).
    - Examine registers for "poison" values (e.g., `0000000000000028` often indicates a NULL pointer dereference with a structure offset).


## Linux distribution specific tasks

Linux distributions have downloadable content that provides the various
files needed for the analysis, even if these are not available naturally on
the local system.
This section only applies if the "DISTRO" field in the "Key Elements" table
is populated.

**Before starting any downloads**, always check whether `oops-workdir/linux`
already exists and already has the relevant remotes and tags configured — a
previous session may have done the setup already. The distro-specific files
include instructions for checking this.

Based on the value of the `DISTRO` field, **read the corresponding file now**
before proceeding — it contains all download, extraction, vmlinux location,
and source-fetch steps for that distribution:

| DISTRO  | File to read |
|---------|--------------|
| Debian  | [references/debian.md](debian.md) |
| Fedora  | [references/fedora.md](fedora.md) |
| Ubuntu  | [references/ubuntu.md](ubuntu.md) |

Do not continue with the analysis until the steps in the distro file have
been completed and `BASEDIR`, `VMLINUX`, and `SOURCEDIR` are populated in
the "Key Elements" table (or recorded as "not available" if genuinely absent).

## General source tree fallback

This section applies in two situations:
1. **No DISTRO matched** (e.g. Arch Linux, custom kernels) — the distro dispatch
   table above has no entry, so there is no distro-specific file to read.
2. **SOURCEDIR is still unset after the distro steps** — the distro file could not
   produce a source tree (e.g. network failure, unsupported version).

In either case, check whether a kernel git tree already exists locally:

```bash
git -C oops-workdir/linux rev-parse --is-inside-work-tree 2>/dev/null
```

If this succeeds, the tree at `oops-workdir/linux` is available. This git tree
is for the **agent's exclusive use** — feel free to change `HEAD`, check out any
branch or tag, add remotes, reset to any commit, or run any other git operation.
Nothing here belongs to a user's working tree; there is no risk of losing work.
Check out the tag or branch that best matches the UNAME:
- For a vanilla-style version like `6.15.1-arch1-2`, try `v6.15.1` first; if
  absent, try `v6.15`.
- For distro kernels with a suffix (e.g. `-300.fc43`), strip the suffix and try
  the upstream tag.

**If the exact tag is not found locally**, the tree may simply be out of date.
Before falling back to an older tag, run:
```bash
git -C oops-workdir/linux remote update
```
This fetches all new tags and branches from all configured remotes without
changing the working tree. Then retry the tag lookup. Only fall back to the
nearest older tag if the exact version is still absent after the update.

Set `SOURCEDIR` to `oops-workdir/linux` in the "Key Elements" table once checked
out to the matching commit, and continue the analysis.

If the directory does not exist or is not a git tree, clone the stable
kernel tree now:

```bash
mkdir -p oops-workdir
git clone https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/ \
    oops-workdir/linux
```

This is a large clone and may take several minutes; proceed once it
completes. Then check out the tag matching UNAME as described above and
set `SOURCEDIR` to `oops-workdir/linux`.

If the clone fails (e.g. no network access), set `SOURCEDIR` to
"not available" and proceed without source code.

## Locating the vmlinux file

If the "Key Elements" table has a "DISTRO" field, first use
the "Linux distribution specific tasks" primitive to prepare distribution
specific kernel files. 

To map addresses back to source code, locate the matching `vmlinux` file:
(replace "UNAME" with the value of the UNAME field in the "Key Elements"
table):
- Check `/boot/vmlinux-UNAME`
- Check `/usr/lib/debug/boot/vmlinux-UNAME`
- If "BASEDIR" is provided in the "Key Elements" table, search for
  `vmlinux-UNAME` inside the directory tree that BASEDIR points to.
  For Debian, the `-dbg` package installs it at
  `BASEDIR/usr/lib/debug/boot/vmlinux-UNAME`.


Add a `VMLINUX` field to the "Key Elements" table with the file's location if it is found.

## Locating a kernel module

Check in `/lib/modules/$(uname -r)` for the module's file (typically ending in `.ko`).

## Mapping backtrace lines to code

**Demand-load: read [mapping.md](mapping.md) now** when starting this step.
That file covers debug binary selection (vmlinux vs module ELF), address-available
and address-unavailable resolution paths (addr2line, gdb, nm, kallsyms),
return-address correction for Format 2 offsets, and inlined function row splitting.

## Reporting a source code function

**Demand-load: read [reporting.md](reporting.md) now** when starting this step.
That file covers the mandatory online URL link, line-number prefixing rules,
approximate `~NNN` prefixes, inlined functions, macros, struct inclusion,
and the ≤20 / >20 line summarization rules.


## Generating HTML output

This primitive can help when asked to generate HTML output instead of the
normal Markdown. If other, more specialized skills for HTML generation are
available, prefer those over this primitive.

**Never write HTML by hand.** Always use pandoc to convert the Markdown report.
Hand-written HTML is harder to maintain and inconsistent with the skill's output
format.

When asked to generate HTML output, first generate a Markdown report as
usual, and then convert to HTML with this command:
```bash
pandoc -s <Markdown file name> -t html -o <HTML file name> -V maxwidth=72em
```

Unless otherwise asked, do not remove the Markdown file after the conversion.

## Fetching an OOPS from a bug tracker

**Demand-load: read [bugtracker.md](bugtracker.md) now** when the user provides
a bug tracker URL or bare bug ID (Launchpad, kernel Bugzilla, Debian BTS, or
Red Hat Bugzilla). That file contains all fetch, extraction, and hand-off steps.

## Transcribing an OOPS from a screenshot or image

**Demand-load: read [image.md](image.md) now** when the user provides a
screenshot, photo, or other image file. That file covers the text-screenshot
path (OCR via `marker_single` or vision fallback), the QR-code path
(drm_panic, v6.10+), provenance recording, and hand-off to the analysis flow.


## Structured archive

When the user has not specified an output location, save the report to the
structured `reports/` archive at the project root (next to `oops-workdir/`).
If the user specifies a location in their prompt or context, use that instead
and skip this primitive.

### Source oops file naming

**The source oops file in the archive is always saved as `oops.txt`**, regardless
of the original filename or source. Never use the caller-supplied filename
directly — doing so risks path traversal or unexpected filenames in the archive.
This applies to all source types: local files, and oops text fetched from bug
trackers or email. For images, use `oops.png` or `oops.jpg` to match the image
type — but never the original filename.

| Source | Path |
|--------|------|
| Launchpad / Ubuntu | `reports/launchpad/<bug-id>/` |
| kernel Bugzilla | `reports/bugzilla.korg/<bug-id>/` |
| Red Hat Bugzilla | `reports/bugzilla.rh/<bug-id>/` |
| Debian BTS | `reports/debian/<bug-id>/` |
| Email (LKML etc.) | `reports/email/<sanitized-msgid>/` |
| Local file | `reports/file/<sha256>/` — see below |
| Other / unknown | `reports/other/<slug>/` (use a short descriptive slug) |

For email, derive the directory name from the raw `MSGID` value: strip angle
brackets and replace `@` with `_`.
Example: `<20240315.abc123@kernel.org>` → `reports/email/20240315.abc123_kernel.org/`

#### Local file archive path

When the oops comes from a local file (e.g. `crash.txt`, `dmesg.log`),
compute the SHA-256 hash of the file to form a stable, content-derived path:

```bash
FILE_SHA256=$(sha256sum <file> | awk '{print $1}')
mkdir -p reports/file/$FILE_SHA256
cp <file> reports/file/$FILE_SHA256/oops.txt
```

Add these rows to the **Key Elements** table:
- `FILE_SHA256` — full hex digest (links to `oops.txt` in the archive)
- `FILE_NAME` — original filename or path as provided by the user

### Files in each report directory

| File | When to create |
|------|----------------|
| `report.md` | Always — the full analysis report |
| `report.html` | Always — generated from `report.md` using pandoc (`pandoc -s report.md -t html -o report.html -V maxwidth=72em`). Never write HTML by hand. |
| `<auto-name>.patch` | When an upstream fix commit is found — run `git format-patch -1 <hash> -o <dir>` and keep the auto-generated filename (e.g. `0001-net-l3mdev-fix-null-deref.patch`) as it is self-documenting. |
| `report.patch` | When the agent creates a **new** suggested fix patch. If multiple candidate patches are produced, use `report.patch` for the best option and `report-alternate-1.patch`, `report-alternate-2.patch`, … for the others. |
| `patch-email.txt` | When a new fix patch was produced — the LKML-ready email (From/Subject/body/tags/Cc/patch). |
| `git-send-email.sh` | Alongside `patch-email.txt` — runnable script with the suggested `git send-email` invocation. |

**Mandatory steps when writing the archive:**

1. Always write `report.md`.
2. Always generate `report.html` with pandoc immediately after.
3. **If an upstream fix commit was identified during the analysis:** run
   `git format-patch -1 <full-hash> -o <archive-dir>` and leave the
   auto-generated filename as-is. This is not optional — do it even if
   the commit is already applied to the reporter's kernel.

### Collision handling

Before writing any files, check whether the target directory already exists:

```bash
[ -d reports/<source>/<id> ] && echo "exists"
```

If it exists and contains a `report.md`, notify the user:
> "A report already exists at `reports/<source>/<id>/report.md`. Overwrite,
> append new findings, or choose a different location?"

Wait for the user's answer before proceeding. If the directory exists but is
empty, proceed without asking.

### TOC update (optional)

If a `reports/README.md` or `reports/index.md` exists, append a one-line
entry for the new report. If it does not exist, do not create it — let the
user decide whether to maintain a top-level index.


