# General Fundamentals Extraction

**Demand-load this file** when starting the General fundamentals extraction step.

The oops may start each line with a timestamp. For the purpose of analysis,
this timestamp is not useful and should be ignored; most of the examples
in this skill are without timestamps.
A line with a timestamp looks like this:
```
[ 1234.567890] BUG: unable to handle kernel paging request at 0000000000000028
```
In this case, `[ 1234.567890] ` is the timestamp for this line. The time
will always be numeric and contained between `[` and `]`.

Sometimes a report contains several consecutive oops reports; this is
natural, once something goes wrong, there will be follow on consequences;
these later oopses generally provide no meaningful information.
Analyze only the first oops report for root cause.

The following subsections describe the "key elements" to extract from the report
and the field names to use. As part of the extraction, create a "Key Elements" table
with the extracted data fields:

| Field | Value | Implication |
| ----- | ----- | ----------- |

Not all rows will have an Implication field.

Rows are added to this table progressively as the analysis proceeds. Expected rows include
(but are not limited to): `UNAME`, `DISTRO`, `DISTRO_VERSION`, `SOURCEDIR`, `MSGID`,
`MSGID_URL`, `BUG_URL`, `IMAGE_SHA256`, `IMAGE_FILE` (added by the image transcription
primitive), `CONFIG_REQUIRED` (added by the **Debug assertion CONFIG_ guard** section
below — the `CONFIG_` option that gates the assertion that fired),
`INTRODUCED-BY` (commit hash link — added by the Bug introduction analysis step
if a key commit is found), and `FIXED-BY` (commit hash link — added by the fix-search step
if an upstream fix is found).


If the user prompt or existing context already tells you where the Linux kernel source tree
is located, store this location in a "SOURCEDIR" row in this table now. Otherwise,
"SOURCEDIR" will be set later by the "Linux distribution specific tasks" primitive.

**Path format for SOURCEDIR and VMLINUX:** Record these as paths relative to
the skill root (e.g. `oops-workdir/linux`, `oops-workdir/syzbot/vmlinux-c1f49dea`),
not as absolute machine paths. Strip any leading machine-specific prefix
(e.g. `/sdb1/arjan/git/oops-skill/`). This keeps reports portable.

### Kernel version
The `UNAME` (the kernel version string) can be found in a line like this:
```
CPU: 2 PID: 1234 Comm: my_driver_test Tainted: G        W         5.15.0-generic #1
```
For this line, the `UNAME` is `5.15.0-generic`.

Another example, for a "not tainted" kernel:
```
CPU: 0 PID: 1234 Comm: insmod Not tainted 4.15.0-rc1+ #1
```
In this example, the `UNAME` is `4.15.0-rc1+`.

The token after the `#` on this line is the build string (e.g. `#29~24.04.1-Ubuntu`
or `#14-Ubuntu`). For most distros it is not material, but the `#` character
serves as a reliable separator, and for Ubuntu kernels the build string is the
**primary distro identifier** (see below).

Always extract the `UNAME` from the crash report; it is a key property used in various
subsequent steps.

Various Linux distributions have special conventions for the `UNAME` field and
the build string that follows `#`. Inspect both to detect the distribution.
If a Linux distribution is detected, add the data to the "Key Elements" table.

| Example UNAME             | Build string example      | DISTRO | DISTRO_VERSION |
| ------------------------- | ------------------------- | ------ | -------------- |
| `6.15.1-arch1-2`          | (any)                     | Arch   |                |
| `6.11.0-1.fc41.x86_64`    | (any)                     | Fedora | fc41           |
| `6.19.10+deb14-amd64`     | (any)                     | Debian |                |
| `5.10.0-debian`           | (any)                     | Debian |                |
| `Debian 6.19.10-1`        | (any)                     | Debian |                |
| `6.14.0-29-generic`       | `#29~24.04.1-Ubuntu`      | Ubuntu | 24.04          |
| `7.0.0-14-generic`        | `#14-Ubuntu`              | Ubuntu | (unknown)      |

**Ubuntu detection rule:** the definitive Ubuntu signal is the build string
ending in `-Ubuntu` (matching the pattern `#<N>-Ubuntu` or
`#<N>~<release>-Ubuntu`). Do not rely on the UNAME suffix alone — Ubuntu ships
many flavors (`-generic`, `-lowlatency`, `-aws`, `-azure`, etc.) and those
suffixes are not unique to Ubuntu.

- If the build string matches `#<N>~<X.Y.Z>-Ubuntu`: set `DISTRO=Ubuntu` and
  `DISTRO_VERSION=<X.Y>` (the Ubuntu release, e.g. `24.04`).
- If the build string matches `#<N>-Ubuntu` (no `~`): set `DISTRO=Ubuntu` and
  leave `DISTRO_VERSION` unknown — the Ubuntu release cannot be derived from the
  header alone.

If a field in the `Debian 6.19.10-1` form is present, please add a
"DEBIAN_VER" row with value `6.19.10-1`.

### Git-describe kernel versions

When a kernel is built directly from a git tree without a clean release tag,
the UNAME often contains a `git describe --long` style suffix:

```
7.0.0-08391-g1d51b370a0f8
```

The format is `<tag>-<N>-g<hash>` where:
- `<tag>` is the nearest upstream tag (e.g. `7.0.0`)
- `<N>` is the number of commits since that tag
- `<hash>` is the abbreviated git commit hash of the exact source tree

**When this pattern is present, use `<hash>` directly as the SOURCEDIR
checkout target** — it is more precise than searching for the nearest tag:

```bash
git -C oops-workdir/linux checkout <hash>
```

Verify the hash exists before checking out:

```bash
git -C oops-workdir/linux cat-file -t <hash>
```

If it exists (returns `commit`), set `SOURCEDIR` to `oops-workdir/linux`
at that exact commit. If it does not exist in the local tree, fall back to
the `<tag>` (e.g. `v7.0`) as the nearest available point.




### Crashing process
The crashing process (`PROCESS` field) can be extracted from the following line:
```
CPU: 2 PID: 1234 Comm: my_driver_test Tainted: G        W         5.15.0-generic #1
```
In this case, the `PROCESS` is `my_driver_test`. The `Comm:` string is
shorthand for the process name and terminates at the `Tainted` /
`Not tainted` marker.


### Kernel modules loaded
The loaded kernel modules should be their own table: "Modules List"
The "Modules List" is typically a list extracted from a line like this:
```
Modules linked in: oops(+) netconsole ide_cd_mod pcnet32 crc32 cdrom 
```
In this case, the "Modules List" table should be:

| Module     | Flags | Backtrace | Location | Flag Implication |
| ---------- | ----- | --------- | -------- | ---------------- |
| oops       | +     |   |  | The module's `module_init` function is likely involved in the root cause. |
| netconsole |       |   |  |  |
| ide_cd_mod |       |   |  |  |
| pcnet32    |       |   |  |  |
| crc32      |       |   |  |  |
| cdrom      |       |   |  |  |

Some flag values provide key information; apply the meanings from the table below to fill the "Flag Implication"
column:

| flag | Meaning   | Flag Implication |
| ---- | --------- | ---------------------------- |
|    + | The crash happened while this module was being loaded | The module's `module_init` function is likely involved in the root cause. |
|    - | The crash happened while this module was being unloaded | The module's `module_exit` function is likely involved in the root cause. |
|    O | Out-of-tree | Source code is not in the mainline kernel tree. | 
|    E | External | Source code is not in the mainline kernel tree. |
|    P | Proprietary | Source code is unavailable. |

Do not create additional implications or interpretations in the "Module List"; limit to key information only.

If the `Modules linked in:` line is absent from the report (this can happen during
very early boot, or when the crash occurred inside the idle task or an early IRQ
handler), create the Modules List table with a single note row and continue:

| Module | Flags | Backtrace | Location | Flag Implication |
| ------ | ----- | --------- | -------- | ---------------- |
| *(module list not available in this report)* | | | | |

The "Backtrace" column will be empty at this stage but will be filled in by the "Backtrace Extraction" primitive.

The "Location" column will be empty at this stage but the "Locating a kernel module" primitive may place the filename to the ".ko" module binary there.

If asked to print or report this table, prioritize listing modules that have a "Y" in the Backtrace column.

### Taint flags

The `TAINT` field indicates the kernel's "taint" state at the time of the crash.
Example 1:
```
CPU: 0 PID: 1234 Comm: insmod Not tainted 4.15.0-rc1+ #1
```
"Not tainted" indicates no flags; the `TAINT` field should be empty.

Example 2:
```
CPU: 2 PID: 1234 Comm: my_driver_test Tainted: G        W         5.15.0-generic #1
```
Here, the taint flags are "G" and "W".
The `TAINT` field should contain a list of resolved flags using the table below (omit rows with empty or "<none>" implications):

| flag | meaning | Implication for the analysis |
| ---- | ------- | ---------------------------- | 
|    G | Only GPL modules | <none> |
|    P | proprietary module loaded | Not all source code will be available. |
|    O | out-of-tree module loaded | Source code for some modules will not be in the standard kernel tree. |
|    E | unsigned module loaded | Source code for some modules will not be in the standard kernel tree. |
|    S | hardware out of spec | Hardware may be unstable; root cause might not be software. |
|    M | machine check | Hardware may be unstable; root cause might not be software. |
|    B | bad memory flags | Hardware may be unstable; root cause might not be software. |
|    D | previous oops | This is not the first crash; it may be a side effect of a previous issue. |
|    W | previous warning | An earlier WARNING occurred; locate it as it may be the root cause. |
|    L | softlockup | Indicates a system stall, thermal issues, or malicious software. |
|    K | live patch | The running code may not match the `vmlinux` file. |

Limit the TAINT field to only the implications and flags from this table, do not add or elaborate beyond this table.



### Hardware name
This section is about the field `HARDWARE`. This is indicated in the following
example line:
```
[ 1234.567894] Hardware name: QEMU Standard PC (i440FX + PIIX, 1996), BIOS 1.13.0-1ubuntu1.1 04/01/2014
```
In this case the `HARDWARE` field should have the value `QEMU Standard PC (i440FX + PIIX, 1996)`.
The same line typically also has information about the `BIOS` in use; which
is an optional field you can collect as well (`1.13.0-1ubuntu1.1 04/01/2014`).



### Email source (MSGID)

If the oops was provided via an email (e.g. from LKML, a mailing list, or a
forwarded bug report), extract the `Message-ID` header value and store it in
two Key Elements rows:

| Field | Value |
|-------|-------|
| MSGID | `<20240315.abc123@kernel.org>` (raw value, including angle brackets) |
| MSGID_URL | `[20240315.abc123@kernel.org](https://lore.kernel.org/r/20240315.abc123@kernel.org)` |

Use `MSGID_URL` (the clickable link form) wherever the message ID is displayed
in the report. Keep the raw `MSGID` value available for use in the
`reports/email/` archive path (see the **Structured archive** primitive).

The `reports/email/` directory name is derived from `MSGID` by stripping angle
brackets and replacing `@` with `_`, for example:
`<20240315.abc123@kernel.org>` → `20240315.abc123_kernel.org`.

### Debug assertion CONFIG_ guard

If the crash site is a debug assertion macro — any of `BUG_ON`, `VM_BUG_ON`,
`VM_BUG_ON_FOLIO`, `VFS_BUG_ON_INODE`, `DRM_MM_BUG_ON`, `WARN_ON`,
`WARN_ON_ONCE`, `WARN_ONCE`, or any `*_BUG_ON*` / `*_WARN*` variant —
determine its `CONFIG_` guard. Use the table below first; only grep the source
tree if the macro is not listed.

**Common macros:**

| Macro | CONFIG_ guard | Notes |
|-------|--------------|-------|
| `BUG()` / `BUG_ON()` | unconditional | Always fires on x86 (`CONFIG_BUG` only suppresses on a few non-x86 arches) |
| `WARN()` / `WARN_ON()` / `WARN_ON_ONCE()` / `WARN_ONCE()` | unconditional | Always fires |
| `VM_BUG_ON()` / `VM_BUG_ON_PAGE()` / `VM_BUG_ON_FOLIO()` / `VM_BUG_ON_VMA()` / `VM_BUG_ON_MM()` | `CONFIG_DEBUG_VM` | No-op when `CONFIG_DEBUG_VM=n` |
| `VM_WARN_ON()` / `VM_WARN_ON_ONCE()` | `CONFIG_DEBUG_VM` | No-op when `CONFIG_DEBUG_VM=n` |
| `VFS_BUG_ON()` / `VFS_BUG_ON_INODE()` | `CONFIG_DEBUG_VFS` | No-op when `CONFIG_DEBUG_VFS=n` |
| `DRM_MM_BUG_ON()` | `CONFIG_DRM_DEBUG_MM` | No-op when `CONFIG_DRM_DEBUG_MM=n` |
| `lockdep_assert_held()` / `lockdep_assert*()` | `CONFIG_LOCKDEP` | Without it, stub uses `__assume_ctx_lock` (compiler hint only — no runtime assertion) |
| `DEBUG_LOCKS_WARN_ON()` | unconditional | Always defined; fires when runtime `debug_locks` variable is set (no CONFIG guard on the macro itself) |
| `__queue_work` WARN (workqueue) | unconditional | The workqueue integrity check is an unconditional `WARN_ONCE` |

If the macro is not in the table above, grep for it:

```bash
# Replace MACRO_NAME with the actual macro, e.g. VFS_BUG_ON_INODE
grep -rn "define MACRO_NAME" oops-workdir/linux/include/ oops-workdir/linux/lib/ \
    oops-workdir/linux/drivers/ oops-workdir/linux/fs/
```

Look for guards of the form `#ifdef CONFIG_X`, `#if IS_ENABLED(CONFIG_X)`, or
a compile-time `if (0)` stub in the non-debug path. Add a `CONFIG_REQUIRED` row
to the Key Elements table:

- Guard found → value is the config symbol, e.g. `CONFIG_DEBUG_VM`
- No guard found → value is `(unconditional — fires in all builds)`
