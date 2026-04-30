# Mapping Backtrace Lines to Code

**Demand-load this file** when starting the Mapping backtrace lines to code step.

(First use the "Locating the vmlinux file" primitive to obtain the `VMLINUX` data field.)

The objective of this primitive is to update the table from the "Backtrace Extraction" section by filling in the "Source Location" column whenever possible.

In addition, if the SOURCEDIR is available, you have access to the full
source code of the kernel for deeper analysis in later steps.

## Batch resolution with backtrace_resolve.py

> ⚠️ **MANDATORY when VMLINUX and SOURCEDIR are both set — run the script before doing anything else in this step.**
>
> Do **NOT** run `addr2line`, `gdb`, `nm`, or any individual source lookup
> on backtrace entries until the script has been run and its output inspected.
> Do **NOT** read any kernel source files manually to find source locations
> while this step is in progress. The script resolves the entire backtrace
> in one pass and produces all the data you need.  Manual per-entry work is
> only permitted for entries the script explicitly marks as `skipped` or
> `note`.
>
> If `VMLINUX` is **not** available, skip the script entirely and use the
> manual per-entry procedures below for all entries.

Whenever both `VMLINUX` and `SOURCEDIR` are set, build the JSON input and
run `backtrace_resolve.py` immediately. It resolves source locations,
inlined frames, function source code, git blame hashes, and a disasm window
for the crash site — replacing dozens of individual tool invocations. Use
its output as the **sole** data source for all entries it resolved; fall
back to the **manual per-entry procedures** further below only for entries
the script could not resolve.

### Building the input JSON

Construct a JSON input file from the Backtrace table. The script is at
`scripts/backtrace_resolve.py` inside the `linux-kernel-oops/` skill directory.

```json
{
  "vmlinux":     "<VMLINUX value from Key Elements>",
  "sourcedir":   "<SOURCEDIR value from Key Elements>",
  "modules_dir": "<BASEDIR>/usr/lib/debug/lib/modules/<UNAME>",
  "entries": [
    {"index": 0, "function": "rcu_do_batch",  "offset": "0x1bc", "size": "0x560", "module": "vmlinux"},
    {"index": 1, "function": "rcu_core",       "offset": "0x17d", "size": "0x3a0", "module": "vmlinux"},
    {"index": 2, "function": "handle_softirqs","offset": "0xd7",  "module": "vmlinux"},
    {"index": 3, "function": "some_func",      "offset": "0x42",  "module": "gfs2"}
  ]
}
```

Field notes:
- `index` — row number in the backtrace table, starting at 0. If RIP is
  listed as the first entry, it is index 0; the call-stack entries follow.
- `module` — use `"vmlinux"` for built-in entries (empty Module column).
  For module entries (non-empty Module column), use the module name (e.g.
  `"gfs2"`). The script searches `modules_dir` for the debug ELF; if
  `modules_dir` is not provided, module entries are skipped with an
  explanatory message.
- `modules_dir` — optional top-level directory to search for module debug
  ELFs (e.g. `BASEDIR/usr/lib/debug/lib/modules/<uname>`). The script
  searches recursively for `<module>.ko.debug` first, then `<module>.ko`,
  handling `_`/`-` name variants automatically.
- `size` — optional but improves the disasm window accuracy; include it
  when the backtrace table has it.
- `address` — optional; include the raw address from the backtrace table
  if present (used for cross-check only, not required for resolution).

Save to a temp file and run, writing the output to **`backtrace.json` in
the report archive directory** (not a temp file — the analyst needs it):

```bash
python3 <path-to-linux-kernel-oops>/scripts/backtrace_resolve.py /tmp/bt_input.json <report_dir>/backtrace.json
```

### Using the output

Parse `<report_dir>/backtrace.json`. For each object in `results`:

| Output field | Use |
|---|---|
| `address_formatted` | **Address** column in backtrace table — already in `"0x... (0x... + 0x...)"` form |
| `source.primary.file` + `.line` | **Source Location** column in backtrace table |
| `source.inlined_frames` | Split the row — see **Inlined function row duplication** below |
| `address_computed` | Raw computed address; use `address_formatted` for the table |
| `function_source.code` (+ `.file`, `.start_line`, `.end_line`) | Pre-fetched source for the **What** analysis — no need to re-read the file |
| `git_blame_hashes` + `recent_commits` | Use directly in the **Bug introduction analysis** step — no need to re-run `git blame` on these entries |
| `blame_details` (first 2 normal entries) | Enriched blame: per-commit subject plus any `Fixes:`/`Cc: stable`/`Link:` trailers extracted from the commit message |
| `fix_candidates` (first 2 normal entries) | Commits in any remote branch whose message contains `Fixes: <blame-hash>` — inspect these first as likely upstream fixes; may contain stable-backport duplicates of the same fix |
| `disasm` (index 0 only) | Disasm window around the crash instruction, already annotated with `<<< crash` |
| `function_type` | `"reporting"` / `"assert"` / `"normal"` — see backtrace.md classification tables. Reporting entries have no source/blame fields. Assert entries have source but no blame. |

### Fallback: when to use the manual procedures below

Use the manual per-entry procedures for any entry where the script output contains:

- `"skipped"` — either `modules_dir` was not provided for a module entry, or the
  module ELF could not be found under `modules_dir`. Handle with the module debug
  ELF path described in the manual section below.
- `"note"` instead of `function_source` — either addr2line returned line 0
  (DWARF incomplete at that address) or the function-boundary heuristic misfired.
  Run the manual addr2line / gdb steps for that entry.
- `source` is `null` — addr2line found nothing; fall back to the manual resolution.

---

## Manual per-entry resolution

For entries not covered by the batch script, iterate over each entry in the
backtrace table individually and follow the steps below.

### Choosing the debug binary for a backtrace entry

- If the **Module** column is **empty**: the function is part of the core kernel.
  Use `VMLINUX` as the debug binary for all address-mapping steps below.
- If the **Module** column is **set** (e.g. `gfs2`): the function lives in a
  loadable module. Use that **module's debug ELF** instead of `VMLINUX`. The
  distro-specific file (e.g. `ubuntu.md`, `debian.md`, `fedora.md`) explains
  where to obtain the module debug file. All `addr2line`/`gdb` commands below
  apply identically — substitute the module debug ELF path for `VMLINUX`.
  If the module's debug ELF is unavailable (e.g. out-of-tree, DKMS, or
  proprietary), note this and record "no debug symbols" in the Source Location
  column for those entries.

The return-address correction rules (offset−1, offset−2, …) apply equally to
module frames.

### Source code for a non-Module line
If the "Module" cell is empty, the function is part of the core kernel (`vmlinux`).

#### Address is available
Use one of the following options in order of preference (replacing `VMLINUX` with the actual file path from the "Key Elements" table):

1. `addr2line -e VMLINUX -f <address>`
2. `gdb VMLINUX -ex "l *<address>"`

Try the first option first; only proceed to the second if the first is unsuccessful.

#### Address is not available
When no address is available (Format 2 backtraces), use the function name and
offset to reconstruct the address from the symbol table of the `vmlinux` file.
Once the base address is found, update the "Backtrace" table Address cell using
the `<final_addr> (<base_addr> + <offset>)` format.

**Option 1 — `nm` + `addr2line` (preferred):**
```bash
# Step 1: look up the base address of the function
nm -n VMLINUX | grep " T <function>"
# Step 2: add the offset (both values are hex) to get the final address
python3 -c "print(hex(0x<base_address> + 0x<offset>))"
# Step 3: resolve to source
addr2line -e VMLINUX -f <computed_address>
```
Record `<computed_address> (<base_address> + 0x<offset>)` in the Address column.


**Option 2 — `gdb` by name (simpler, one step):**
```bash
gdb VMLINUX -ex "info line *((<function>)+<offset>)" -batch
```
Replace `<function>` and `<offset>` with the values from the backtrace entry.
This works because `gdb` can resolve a symbol by name without needing the raw
address first.

**Option 3 — live system only:**
If the analysis is being done on the machine that crashed and `/proc/kallsyms`
is still readable, the runtime address of the function is available there:
```bash
grep " <function>$" /proc/kallsyms
```
Then add the offset and pass the result to `addr2line` as in Option 1.

#### Return-address correction for Format 2 offsets

Format 2 backtrace offsets are **return addresses** — the address of the
instruction *immediately after* the call instruction, not the call itself.
This means that resolving `function+0xNN` with `gdb` or `addr2line` will
give a source line that is one instruction *past* the actual call site,
which may map to the next statement in the source (or even a different
function if the compiler optimised the tail).

To find the true call-site source line, probe `offset-1`, `offset-2`,
... down to `offset-5` until you get a stable source location:

```bash
# probe -1 first; keep going if gdb reports the next statement
gdb -batch VMLINUX -ex "info line *((function)+(offset-1))"
gdb -batch VMLINUX -ex "info line *((function)+(offset-2))"
# ... up to offset-5 if needed
```

Take the first result that maps to a *different* (earlier) source line than
the `+offset` probe. That is the actual call site. Update the "Source
Location" column in the backtrace table with this corrected line.

**Example:**  `rcu_do_batch+0x1bc` resolves to `preempt.h:27` (inlined
epilogue), but `+0x1bb` resolves to `kernel/rcu/tree.c:2605` — the real
call site.

### Inlined function row duplication

When `gdb` or `addr2line` resolves a backtrace entry to source code inside a
*different* function (i.e. an inlined function), **split the single backtrace
row into two consecutive rows**:

| Row | Function column | Source location | Notes |
|-----|-----------------|-----------------|-------|
| Top (inner) | name of the **inlined** function | file and line inside the inlined function | This is what actually executed |
| Bottom (outer) | original backtrace function name | file and line of the **call site** in the outer function | The compiler inlined the inner function here |

Mark the top row with `(inlined)` appended to the Function name so it is
visually distinct, for example `preempt_disable (inlined)`.

The bottom row retains the original address, offset, size, context, and module
values. The top row inherits the same module but leaves address/offset/size
blank (the inlined function has no independent frame).

**Example** — before:

| Address | Function | Offset | Size | Module | Source location |
|---------|----------|--------|------|--------|-----------------|
| 0xffffffff81234abc | `rcu_do_batch` | `0x1bc` | `0x300` | *(built-in)* | `arch/x86/include/asm/preempt.h:27` |

After splitting:

| Address | Function | Offset | Size | Module | Source location |
|---------|----------|--------|------|--------|-----------------|
| | `preempt_disable (inlined)` | | | *(built-in)* | `arch/x86/include/asm/preempt.h:27` |
| 0xffffffff81234abc | `rcu_do_batch` | `0x1bc` | `0x300` | *(built-in)* | `kernel/rcu/tree.c:2605` |
