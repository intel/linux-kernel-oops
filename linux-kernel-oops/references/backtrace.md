# Backtrace Extraction

**Demand-load this file** when starting the Backtrace extraction step.

A call trace can have multiple formats. The goal of this primitive is to
provide a unified Markdown table named "Backtrace", with one row per usable trace line.

| Address | Function | Offset | Size | Context | Module | Source location |
| ------- | -------- | ------ | -----| ------- | ------ | --------------- |

Not all fields are available in all formats; if a field is missing, leave the column blank.
The "Source location" column is generally empty after this step and filled in
by the "Mapping backtrace lines to code" primitive — except where the rule
below provides the location directly.
The "Context" column defaults to a value of "Task".

**Address column format:** When both the final (absolute) address and the function base
address are known, use the format:

```
<final_addr> (<base_addr> + <offset>)
```

This makes it easy to both use the address directly with `addr2line` and to
understand which function and at what offset it falls. When only the final
address is known (no base), show just `<final_addr>`. When neither is
available yet (Format 2 before symbol resolution), leave the cell blank.

### First item: The crash location
The first item in the table should be the function where the crash actually occurred.
Example 1:
```
RIP: 0010:generic_make_request_checks+0x3c4/0x5a0
```
The `RIP:` field indicates the Instruction Pointer at the time of the crash. In this example,
the "Function" is `generic_make_request_checks`, the "Offset" is `0x3c4`, and the "Size"
is `0x5a0`. The RIP register value (from the register dump) gives the final address directly;
the base can be computed as `RIP − offset`. Use the full format in the Address column:
`<RIP_value> (<RIP_value - offset> + 0x3c4)`.

Example 2:
```
RIP: 0010:ucsi_reset_ppm+0x1a8/0x1c0 [typec_ucsi]
```
In this example, the "Function" is `ucsi_reset_ppm`, the "Offset" is `0x1a8`, the "Size"
is `0x1c0`, and the "Module" is `typec_ucsi`.

If the `RIP:` register has a value of `0`, include it in the table; this indicates a NULL function pointer was followed and is an important piece of evidence for later analysis.

**Source location for WARNING crashes (free, no tooling needed):** When the crash
type is `WARNING`, the warning header line encodes the exact source location of
the `WARN()` call site. Use it to fill the "Source location" cell for the RIP
entry immediately, without waiting for the "Mapping backtrace lines to code"
primitive. Example:
```
WARNING: CPU: 4 PID: 33 at drivers/usb/typec/ucsi/ucsi.c:1380 ucsi_reset_ppm+0x1a8/0x1c0 [typec_ucsi]
```
Here the "Source location" for `ucsi_reset_ppm` is `drivers/usb/typec/ucsi/ucsi.c:1380`.

### Format 1: Braced addresses
```
Call Trace:
 [<ffffffff810020d0>] do_one_initcall+0x50/0x190
 [<ffffffff81156a33>] load_module+0x2213/0x2940
```
In this format, the bracketed value is the **final (absolute) address** of the instruction.
The function base address can be computed as `final_addr − offset`. Use the full
`<final> (<base> + <offset>)` format for the Address column:

| Address | Function | Offset | Size |
|---------|----------|--------|------|
| `ffffffff810020d0 (ffffffff81002080 + 0x50)` | `do_one_initcall` | `0x50` | `0x190` |
| `ffffffff81156a33 (ffffffff81155820 + 0x2213)` | `load_module` | `0x2213` | `0x2940` |

This example contains no "Module" data.

### Format 2: Raw symbols
```
Call Trace:
   generic_make_request+0x6a/0x3b0
   submit_bio+0x40/0x130
   ? guard_bio_eod+0x43/0x120
   submit_bh_wbc+0x15e/0x190
```
In this case, no address is provided. Leave the Address column blank at this stage; it
will be filled in by the "Mapping backtrace lines to code" primitive once the function's
base address is resolved from the symbol table (nm or /proc/kallsyms).

**Important:** Refer to the subsection about the "?" markers below.

### Format 3: Annotated with source locations (syzbot / newer kernels)

Some kernels (and all syzbot reports) pre-annotate backtrace lines with
`file:line` taken directly from DWARF. The kernel also expands inlined
functions as separate lines marked `[inline]`. Example:

```
__dump_stack lib/dump_stack.c:94 [inline]
dump_stack_lvl+0x100/0x190 lib/dump_stack.c:120
__might_resched.cold+0x1ec/0x232 kernel/sched/core.c:9162
shmem_undo_range+0x447/0x1570 mm/shmem.c:1150
shmem_truncate_range mm/shmem.c:1277 [inline]
shmem_evict_inode+0x3f3/0xc40 mm/shmem.c:1407
iput_final fs/inode.c:1960 [inline]
iput.part.0+0x605/0xf50 fs/inode.c:2009
```

Two sub-patterns appear in Format 3:

1. **Annotated non-inlined**: `function+offset/size file:line`
   — normal entry with offset/size AND a source annotation appended.
   Fill the "Source location" column immediately from the annotation.
   Leave the Address column blank (to be filled by the mapping primitive).

2. **Inlined**: `function file:line [inline]`
   — no offset/size; has source annotation and `[inline]` suffix.
   The function was inlined into the **next non-inline entry below it**.

**How to handle inlined entries in the table:**

Include inlined entries as table rows. Fill "Source location" immediately.
Append `(inlined)` to the Function name so they are visually distinct.
Leave Address, Offset, and Size blank.

**Important:** Do **not** create a `backtrace_resolve.py` JSON entry for
`[inline]` rows. They have no independent binary address and will appear
naturally as `source.inlined_frames` on the parent when `addr2line -i` runs
against the parent's address. The JSON `index` counter is incremented **only**
for non-inline entries; table row numbers will differ from JSON indices when
inline rows are present.

**Inline ownership rule:** a run of consecutive `[inline]` rows immediately
above a non-inline entry all belong to that non-inline entry as its inline chain.

**Composing with module/build-ID rules:** Format 3 layers on top of all existing
rules. A Format 3 non-inline entry may still have `[module]` or
`[module build-id-hash]` brackets after the offset/size and before the
`file:line` annotation — parse the module and build-ID first, then take the
remaining `file:line` as the source annotation.

**`source_hint` field for the script:** When building the JSON input for
`backtrace_resolve.py` from a Format 3 backtrace, add the pre-annotated source
location as an optional `source_hint` field:

```json
{"index": 0, "function": "shmem_undo_range", "offset": "0x447", "size": "0x1570",
 "module": "vmlinux", "source_hint": "mm/shmem.c:1150"}
```

The script uses `source_hint` as a fallback if `addr2line` returns nothing
(e.g. DWARF is sparse). When a full vmlinux is available, `addr2line` runs
normally and `source_hint` is ignored — so inline frame recovery is unaffected.

### Format variation: Interrupt and Task markers
All formats (1, 2, and 3) may encounter Task and IRQ markers, as per this
example:
```
[    6.292320]  <IRQ>
[    6.292321]  rcu_do_batch+0x1bc/0x560
[    6.292327]  rcu_core+0x17d/0x3a0
[    6.292330]  handle_softirqs+0xd7/0x310
[    6.292333]  __irq_exit_rcu+0xbc/0xe0
[    6.292335]  sysvec_apic_timer_interrupt+0x71/0x90
[    6.292339]  </IRQ>
[    6.292340]  <TASK>
[    6.292341]  asm_sysvec_apic_timer_interrupt+0x1a/0x20
```
The "<IRQ>" section may not be present, and the backtrace may start with a
"<TASK>" marker.
When encountering these markers, the rules are as follows:
1. Do not put the markers (including their "</" forms) in the table.
2. All entries after the "<IRQ>" but before the "<TASK>" marker will get "IRQ" in the "Context" column.
3. All entries after the "<TASK>" marker will get the "Task" value in the "Context" column.
4. If the markers are absent, every entry gets a "Task" value in the "Context" column.


### Module data
Module data is indicated by `[` and `]` brackets after the offset part of
the entry:
```
my_driver_ioctl+0x45/0x80 [my_driver]
```
In this trace line, the "Module" field should contain `my_driver`. This indicates the function is part of a loadable module rather than the core kernel (vmlinux file), which is essential for locating the correct source code.

For each module found, update the "Module List" table to have a "Y" in the "Backtrace" column for the module in question.

#### Build ID hashes (newer kernels, 6.15+)

Newer kernel versions append a build ID hash after the module name inside the brackets:
```
ucsi_init_work+0x3b/0x9c0 [typec_ucsi a58e34a66711100478075e9035267b4c0b538e88]
```
In this case, the "Module" is `typec_ucsi` (the first token inside the brackets) and the
long hex string is a **build ID hash** — a SHA1 of the module binary used to match it to
its debug symbols. It is **not** a second module name. Record only the module name
(`typec_ucsi`) in the "Module" column; note in the row that a build ID hash is present.
This hash can be used to verify that a downloaded debug package matches the running module.


### Handling "?" markers (unreliable entries)
Entries marked with a "?" indicate that the stack unwinder was not confident about the entry.

Follow these rules for inclusion:
1. **If there are more than 2 high-confidence lines** (those without a "?"): Exclude all lines marked with a "?".
2. **If there are 2 or fewer high-confidence lines**: Include the "?" lines in the output table to provide additional context.

---

## Backtrace entry classification

Some functions in the call trace are not crash sites — they exist to report
or detect the crash. `backtrace_resolve.py` classifies every entry and sets
a `function_type` field in the output. The analysis should treat each type
differently:

### Reporting functions — skip entirely

These functions exist **only to emit the crash message**. They appear at the
top of the stack before the real crash site. Skip them for source analysis,
blame, and fix candidates. The analysis starts at the first non-reporting
entry.

| Function | Notes |
|---|---|
| `__dump_stack` | Core stack dump emitter |
| `dump_stack` | Wrapper |
| `dump_stack_lvl` | Wrapper with log level |
| `show_regs` | Register dump emitter |
| `show_stack` | Architecture stack printer |
| `print_address_description` | KASAN address description |
| `kasan_report` | KASAN UAF/OOB reporter |
| `kasan_report_invalid_free` | KASAN double-free reporter |
| `kasan_report_access` | KASAN access reporter |
| `__kasan_report` | KASAN internal reporter |
| `kasan_bug_type_str` | KASAN bug type formatter |
| `ubsan_epilogue` | UBSAN error epilogue |
| `ubsan_handle_type_mismatch_v1` | UBSAN type mismatch handler |
| `print_unlock_imbalance_bug` | Lock imbalance error reporter |

### Assert / canary functions — show source, skip blame

These functions **detect a violated precondition** but are not the root
cause. Include their source code in the report (to show where the assert
fired), but do not generate blame or fix_candidates for them. The caller
that violated the precondition is the real crash site.

| Function | Notes |
|---|---|
| `might_sleep` | Sleepability precondition check |
| `__might_sleep` | Internal variant |
| `might_resched` | Reschedule precondition check |
| `__might_resched` | Internal variant |
| `cant_sleep` | Inverse sleepability check |
| `cant_migrate` | Migration precondition check |
| `kasan_check_range` | KASAN memory range validator |
| `__asan_memcpy` | ASan-instrumented memcpy wrapper |
| `kmemdup_noprof` | Memory-profiling kmemdup variant |

> **Keep these tables in sync with `REPORTING_FUNCTIONS` and
> `ASSERT_FUNCTIONS` in `backtrace_resolve.py`** — they are the
> authoritative source of truth for the classification.

### Compiler-generated function suffixes

The compiler may emit specialised variants of a function under a modified
name. Common suffixes seen in kernel backtraces:

| Suffix pattern | Meaning |
|---|---|
| `.part.N` | Partial/outlined function body split by the compiler |
| `.constprop.N` | Constant-propagation specialisation |
| `.isra.N` | Inter-procedural scalar replacement of aggregates |
| `.cold` or `.cold.N` | Cold (rarely executed) code path outlined to a separate section |
| `.llvm.N` | LLVM-internal variant |

**Rule for source code lookup:** strip the suffix before looking up the
function in a source file, in `REPORTING_FUNCTIONS`, `ASSERT_FUNCTIONS`, or
any other name-based table. The suffix is a compiler artefact — the source
code always uses the base name. For example, `__might_resched.cold` →
look up `__might_resched`.

**Rule for reporting and assembly:** keep the full suffixed name in the
Backtrace table, in disassembly, and in any address-based lookups. The
suffix identifies a specific binary symbol; stripping it would resolve to
the wrong address.
