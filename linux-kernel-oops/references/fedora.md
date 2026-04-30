# Fedora — Distribution-Specific Tasks

This file is loaded on demand by the **Linux distribution specific tasks**
primitive in `primitives.md` when `DISTRO = Fedora`.

On Fedora the UNAME format looks like `6.11.0-1.fc41.x86_64`.

---

## Downloading the debuginfo package

Create a directory `oops-workdir/fedora/rpms/` and use it as a cache for all
downloaded RPM files (skip the download if the file is already present).

**If the user says they don't have debuginfo RPMs available:** do not treat
this as a reason to skip. The RPM is always downloadable from Koji at no cost.
Guide the user through the download steps below. Do not mark VMLINUX or
BASEDIR as "not available" until you have actually attempted the download and
confirmed it failed (e.g. no network, 404, insufficient disk space). Without
the `.ko.debug` files from the `kernel-debuginfo` RPM, backtrace-to-source
mapping is not possible and the analysis will be significantly degraded.

The Fedora debuginfo repos provide `kernel-debuginfo` packages. If the
analysis machine is running the same kernel as the oops, install with:
```bash
dnf debuginfo-install kernel-$(uname -r)
```

More commonly (analyzing a crash from another machine), download the RPM
directly. The `DISTRO_VERSION` field (e.g. `fc43`) gives the Fedora release
number.

The debuginfo packages are in the `debug/` sub-tree, not the main packages
tree. Browse the debug package index for that release:
```
https://mirror.fcix.net/fedora/linux/updates/<release>/Everything/x86_64/debug/Packages/k/
```
For example, for `fc43` use release `43`. Find the file named
`kernel-debuginfo-<ver>.x86_64.rpm` matching the UNAME and download it:
```bash
curl -L -o oops-workdir/fedora/rpms/kernel-debuginfo-<ver>.<arch>.rpm \
  https://kojipkgs.fedoraproject.org/packages/kernel/<version>/<release>/<arch>/kernel-debuginfo-<ver>.<arch>.rpm
```

The mirror only retains the **current** kernel for each release. If the UNAME
does not match the current kernel on the mirror, use the Koji package server
directly (it retains all builds):
```
https://kojipkgs.fedoraproject.org/packages/kernel/<version>/<release>/<arch>/
```
For example, for UNAME `6.17.7-300.fc43.x86_64`:
- `<version>` = `6.17.7`
- `<release>` = `300.fc43`
- `<arch>` = `x86_64`

If the kernel is old enough to have been archived, try:
```
https://dl.fedoraproject.org/pub/archive/fedora/linux/updates/<release>/Everything/x86_64/debug/Packages/k/
```

## Extracting the RPM

Create the directory `oops-workdir/fedora/files/` and extract the RPM into it:
```bash
mkdir -p oops-workdir/fedora/files
pushd oops-workdir/fedora/files
rpm2cpio ../rpms/kernel-debuginfo-<ver>.<arch>.rpm | cpio -i -d -u
popd
```
Then add a row to the "Key Elements" table for `BASEDIR`, and set it to
`oops-workdir/fedora/files/`.

## vmlinux and module debug symbol locations

**vmlinux:** The `kernel-debuginfo` RPM may or may not include `vmlinux`
depending on the Fedora release. Check for it at:
```
BASEDIR/usr/lib/debug/lib/modules/<UNAME>/vmlinux
```
If found, set `VMLINUX` in the "Key Elements" table to this path. If not
present, set `VMLINUX` to "not available" — this only limits addr2line
resolution for in-kernel (non-module) backtrace entries.

**Module `.ko.debug` files:** Module debug symbols are extracted from the same
`kernel-debuginfo` RPM and install under:
```
BASEDIR/usr/lib/debug/lib/modules/<UNAME>/kernel/<subsystem>/<module>.ko.debug
```
These can be used directly with gdb for offset-to-line mapping of any
module-level backtrace entry:
```bash
gdb -batch <module>.ko.debug -ex "info line *(fn+offset)"
```
This is sufficient for module crash analysis even when `vmlinux` is absent.

### Obtaining the companion `.ko` for disassembly (entry 0 in a module)

The `.ko.debug` file has `NOBITS` `.text` sections — the actual code bytes
were stripped out. `objdump -d` against `.ko.debug` produces no instructions.
`backtrace_resolve.py` will set `disasm: null` and a `disasm_note` for entry 0
when no companion `.ko` is found.

**Do this only when entry 0 is in a kernel module** (not vmlinux) and you need
a disassembly window for the crash instruction.

Download the `kernel-modules` RPM from Koji — same version/release/arch as the
`kernel-debuginfo` RPM:
```bash
curl -L -o oops-workdir/fedora/rpms/kernel-modules-<ver>.<arch>.rpm \
  https://kojipkgs.fedoraproject.org/packages/kernel/<version>/<release>/<arch>/kernel-modules-<ver>.<arch>.rpm
```

Extract **only** the module you need (avoids unpacking the full ~200 MB RPM):
```bash
pushd oops-workdir/fedora/files
rpm2cpio ../rpms/kernel-modules-<ver>.<arch>.rpm \
  | cpio -i -d -u --no-absolute-filenames \
    "./lib/modules/<UNAME>/kernel/<subsystem>/<module>.ko"
popd
```

The extracted file lands at:
```
BASEDIR/lib/modules/<UNAME>/kernel/<subsystem>/<module>.ko
```

`backtrace_resolve.py` will automatically detect this companion path
(`_companion_ko()`) and use it for disassembly on the next run. No input
JSON change is needed.

## Fetching kernel source

**This step is required.** Do not skip it or substitute a source tree from a
different kernel version — Fedora carries patches that differ from mainline
and from other distributions, and using the wrong source tree will produce
misleading analysis.

Fedora makes its kernel sources available via git from the CKI project at
`https://gitlab.com/cki-project/kernel-ark`.

**If a git tree already exists at `oops-workdir/linux`**, check whether the
Fedora remote and the needed tag are already present before doing any fetch —
a previous session may have already set this up:
```bash
# Check if the remote is already configured (prints URL or errors silently)
git -C oops-workdir/linux remote get-url fedora 2>/dev/null \
  || git -C oops-workdir/linux remote add fedora https://gitlab.com/cki-project/kernel-ark

# Check if the tag is already fetched, fetch it only if missing
git -C oops-workdir/linux rev-parse --verify 'refs/tags/<tag>' 2>/dev/null \
  || git -C oops-workdir/linux fetch fedora 'refs/tags/<tag>:refs/tags/<tag>'
```

**If no git tree exists yet**, clone it directly:
```bash
mkdir -p oops-workdir
git clone https://gitlab.com/cki-project/kernel-ark oops-workdir/linux
```

### Finding the right git tag

Tags have the form `kernel-<version>-<build>`. Strip the `.fc<N>.x86_64`
suffix from the UNAME, then look for an exact tag match. For example, UNAME
`6.11.0-1.fc41.x86_64` maps to tag `kernel-6.11.0-1`.

**Important:** The RPM build number in the UNAME does not always match the
build number used in the CKI tag. If no exact tag exists for the stripped
UNAME, search for any tag with the same kernel version using the GitLab API:
```bash
curl -s "https://gitlab.com/api/v4/projects/cki-project%2Fkernel-ark/repository/tags?search=kernel-<version>&per_page=20" \
  | python3 -c "import json,sys; [print(t['name']) for t in json.load(sys.stdin)]"
```
Use the tag that matches the kernel version. For example, UNAME
`6.17.7-300.fc43.x86_64` has no tag `kernel-6.17.7-300`, but the API returns
`kernel-6.17.7-0` — use that.

### Checking out the tag

```bash
git -C oops-workdir/linux checkout kernel-<version>-<build>
```

Set `SOURCEDIR` to `oops-workdir/linux` in the "Key Elements" table.
