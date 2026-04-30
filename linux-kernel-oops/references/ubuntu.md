# Ubuntu — Distribution-Specific Tasks

This file is loaded on demand by the **Linux distribution specific tasks**
primitive in `primitives.md` when `DISTRO = Ubuntu`.

On Ubuntu the UNAME format looks like `5.13.0-27-generic`.

---

## Downloading the debug package

Ubuntu debug symbol packages are hosted on the Ubuntu debug symbol archive.
The package filename follows one of two patterns depending on architecture:

- `amd64`: `linux-image-unsigned-<uname>-dbgsym_<ver>_amd64.ddeb`
- Other arches: `linux-image-<uname>-dbgsym_<ver>_<arch>.ddeb`

The package version `<ver>` is derived from the oops header line:
```
CPU: ... Comm: ... 6.14.0-29-generic #29~24.04.1-Ubuntu
```
The formula is `<kernel-base>-<abi>.<rebuild>~<ubuntu-release>`, where:
- `<kernel-base>` = base kernel version from UNAME (e.g., `6.14.0`)
- `<abi>` = ABI suffix from UNAME (e.g., `29` from `6.14.0-29-generic`)
- `<rebuild>` = number after `#` (e.g., `29` from `#29~24.04.1-Ubuntu`)
- `<ubuntu-release>` = number after `~` (e.g., `24.04.1` from `~24.04.1-Ubuntu`)

Example: UNAME `6.14.0-29-generic`, header `#29~24.04.1-Ubuntu` →
package version `6.14.0-29.29~24.04.1`, filename
`linux-image-unsigned-6.14.0-29-generic-dbgsym_6.14.0-29.29~24.04.1_amd64.ddeb`.

**If the build string has no `~` (e.g. `#14-Ubuntu`):** the package version
cannot be derived from the header alone. Try the following steps in order to
find it:

1. **Search ddebs.ubuntu.com pool** for filenames matching the UNAME:
   ```bash
   curl -s http://ddebs.ubuntu.com/pool/main/l/ | grep -o 'href="[^"]*"' | grep "<uname>"
   ```
   Try subdirectories such as `linux/`, `linux-hwe-*/` as needed.
2. **Search Launchpad package publishing pages** for the kernel source package,
   e.g. `https://launchpad.net/ubuntu/+source/linux` — look for a published
   binary matching the UNAME.
3. **Ask the user** if they have the exact package version or Ubuntu release
   (from `/etc/os-release`, `lsb_release -a`, `dpkg -l linux-image-*`, or
   `/proc/version_signature` on the crashed machine).
4. If none of the above yields the version, record `VMLINUX=not available` and
   proceed without debug symbols. Source-mapping accuracy will be reduced.

**The debug package is always required for source mapping.** Ubuntu ships
a usable `System.map` in the standard kernel package, but `vmlinuz`
carries no ELF symbols. The `vmlinux` ELF image needed for `addr2line`
and `gdb` is only in the `-dbgsym` package.
Always include the `-dbgsym` package in the download set — it is large
(~1 GB) but cached in `oops-workdir/ubuntu/debs/` so it is only fetched
once per kernel version.

**If the user says they don't have the debug package installed:** do not
treat this as a reason to skip. The package is always downloadable at no
cost. Guide the user through the download steps below. Do not mark
VMLINUX as "not available" until you have actually attempted the download
and confirmed it failed (e.g. no network, insufficient disk space).
Without the vmlinux from the -dbgsym package, backtrace-to-source mapping
is not possible and the analysis will be significantly degraded.

Create a directory in the working space, `oops-workdir/ubuntu/debs/` and
use that directory to download the package if it does not exist there yet
(use this directory as a cache for future analysis).

### Finding and downloading the package

Try these sources in order, stopping at the first that works:

**Option 1 — ddebs.ubuntu.com pool** (most recent kernels only):
Browse `http://ddebs.ubuntu.com/pool/main/l/` and look for a
subdirectory matching the kernel variant (e.g. `linux-hwe-6.14/`,
`linux/`). Filter for the UNAME and `amd64`. If the package is listed,
download it with `wget` or `curl -O`.

**Option 2 — Launchpad** (all published kernels, including older ones):
Construct the direct URL and download:
```bash
wget "https://launchpad.net/ubuntu/+archive/primary/+files/<filename>"
```
where `<filename>` is derived as described above (e.g.
`linux-image-unsigned-6.14.0-29-generic-dbgsym_6.14.0-29.29~24.04.1_amd64.ddeb`).
Launchpad redirects to `launchpadlibrarian.net` which holds the file.

**Option 3 — apt on a matching system** (if running the same kernel):
```bash
sudo apt-get install linux-image-$(uname -r)-dbgsym
```
This installs directly to `/usr/lib/debug/boot/`; skip the extraction
step and set `BASEDIR` to `/`.

**Disk space check — do this before downloading or extracting.** The
`-dbgsym` package alone is ~1 GB to download and expands to roughly 3 GB
unpacked. Check that the filesystem containing `oops-workdir/` has at
least 3 GB free:
```bash
df -h oops-workdir/
```
If free space is below 3 GB, stop and tell the user how much space is
available and how much is needed, and ask them to free up space before
continuing.

## Extracting the package

Create the directory `oops-workdir/ubuntu/files/`.

**Full extraction** (needed when you require `vmlinux` or many modules):
```bash
dpkg-deb -x <full path to the .ddeb file> oops-workdir/ubuntu/files
```
Set `BASEDIR` to `oops-workdir/ubuntu/files/`.

**Targeted extraction** (faster when only one module is needed — e.g. for a
single-module backtrace): stream the package filesystem and extract just the
file you need, letting tar preserve the full internal path:
```bash
dpkg-deb --fsys-tarfile <full path to the .ddeb file> | tar -x \
  -C oops-workdir/ubuntu/files \
  ./usr/lib/debug/lib/modules/<UNAME>/kernel/<subdir>/<module>.ko.zst
```
Note: do **not** use `--strip-components` here — it does not apply correctly
when extracting a single named file from a pipe. The file will be placed at
its full path inside `oops-workdir/ubuntu/files/` (e.g.
`oops-workdir/ubuntu/files/usr/lib/debug/lib/modules/<UNAME>/kernel/...`).
Set `BASEDIR` to `oops-workdir/ubuntu/files/` as usual.

## vmlinux and System.map locations

The `-dbgsym` package extracts `vmlinux` to:
```
BASEDIR/usr/lib/debug/boot/vmlinux-<UNAME>
```
Set `VMLINUX` in the "Key Elements" table to this path.

The `-dbgsym` package also contains per-module debug symbol files at:
```
BASEDIR/usr/lib/debug/lib/modules/<UNAME>/kernel/**/*.ko.zst
```
These are always compressed (`.ko.zst`). They must be decompressed with
`zstd -d` before use with `gdb` or `addr2line` — see the "Using module debug
symbols" section below.

**The `-dbgsym` package does not include `System.map`.** Ubuntu ships a
usable copy in the standard kernel package. If analyzing on the machine
that crashed (or one with the same kernel installed), use:
```
/boot/System.map-<UNAME>
```
Otherwise, download the standard `linux-image-unsigned-<UNAME>` package
from `https://archive.ubuntu.com/ubuntu/pool/main/l/` (find the correct
subdirectory for the kernel variant) and extract it the same way as the
`-dbgsym` package. The `System.map` will be at
`BASEDIR/boot/System.map-<UNAME>`.

## Using module debug symbols for module backtrace entries

For backtrace entries tagged `[module_name]` (e.g. `gfs2_trans_add_revoke+0x2b/0x50 [gfs2]`),
the relevant debug binary is the **module's debug ELF**, not `vmlinux`.

The `-dbgsym` package includes per-module debug files at:
```
BASEDIR/usr/lib/debug/lib/modules/<UNAME>/kernel/**/<module>.ko.zst
```
**Module debug files in the ddeb are always compressed (`.ko.zst`)** and must
be decompressed before use — tools like `gdb` and `addr2line` cannot read
compressed ELF files:
```bash
zstd -d <module>.ko.zst -o <module>.ko
```

**Note:** modules on a running Ubuntu system (in `/lib/modules/<UNAME>/`) may
also be compressed (`.ko.zst` or `.ko.xz` depending on the Ubuntu release).
If you locate a module on the live system instead of extracting from the ddeb,
check whether it is compressed and decompress it the same way before use.
Then use the decompressed `.ko` exactly as you would use `VMLINUX` for core-kernel
entries — substitute it in all `addr2line` and `gdb` commands:
```bash
# nm + addr2line (preferred)
nm -n <module>.ko | grep " T <function>"
gdb <module>.ko -ex "info line *((<function>)+<offset>)" -batch
```
Apply the same return-address correction rules (offset−1, offset−2, …) as for
core-kernel entries.

If the module is not present in the `-dbgsym` package (e.g. out-of-tree, DKMS,
or proprietary module — check taint flags), note "no debug symbols available"
in the Source Location column for those backtrace entries.

## Fetching kernel source

> **Important:** Always use Ubuntu-specific kernel source for Ubuntu oopses.
> Do **not** use the mainline Linux git tree (`oops-workdir/linux`) as a
> substitute, even when the kernel base version matches a mainline tag (e.g.
> `v7.0`). Ubuntu applies patches that may change line numbers, struct layouts,
> and function implementations relative to mainline. Results obtained from
> mainline source will be unreliable.

`apt-get source` always extracts into the **current working directory**,
so it must be run from inside the target directory. Create
`oops-workdir/ubuntu/src/` and run the command from there:
```bash
mkdir -p oops-workdir/ubuntu/src
cd oops-workdir/ubuntu/src
apt-get source linux-image-<UNAME>
```
Check if the tree already exists from prior runs and skip this extraction
for efficiency as needed.

If `apt-get source` fails with "E: You must put some 'deb-src' URIs in your
sources.list", enable source repositories first:
```bash
sudo sed -i 's/^# deb-src/deb-src/' /etc/apt/sources.list
sudo apt-get update
```
If that is not possible (e.g. the user is not on an Ubuntu system), the Ubuntu
kernel source package can be downloaded directly from Launchpad:
`https://launchpad.net/ubuntu/+source/linux` — find the matching version,
download the `.dsc` and `.tar.*` files, and unpack with `dpkg-source -x`.

**If the Ubuntu series is known** (e.g. `resolute`, `noble`, `jammy` — from
`DISTRO_VERSION`, the Launchpad source page, or `/etc/os-release` on the
crashed machine), the Ubuntu kernel is also available as a git tree. Add it
as a remote to the existing `oops-workdir/linux` git tree and fetch only the
branch you need:
```bash
git -C oops-workdir/linux remote add ubuntu-<series> \
    git://git.launchpad.net/~ubuntu-kernel/ubuntu/+source/linux/+git/<series>
git -C oops-workdir/linux fetch ubuntu-<series> Ubuntu-<package-version> --depth=1
git -C oops-workdir/linux checkout FETCH_HEAD
```
Replace `<series>` with the Ubuntu series name (e.g. `resolute`, `noble`) and
`<package-version>` with the full package version (e.g. `Ubuntu-7.0.0-14.14`).
Using `ubuntu-<series>` as the remote name (rather than a generic `ubuntu`)
avoids clashes when multiple series remotes are added to the same tree. Set `SOURCEDIR` to
`oops-workdir/linux` once checked out.

This is preferred over `apt-get source` when a git tree is already present,
as it avoids a separate extraction directory and gives full git history.

> **TODO**: Confirm the name of the extracted source subdirectory from a
> live example (expected: `linux-<base-version>/`, e.g. `linux-5.13.0/`
> for UNAME `5.13.0-27-generic`). Update this section once confirmed.

Set `SOURCEDIR` in the "Key Elements" table to the full path of the
extracted source directory.
