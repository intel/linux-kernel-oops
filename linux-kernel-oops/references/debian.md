# Debian — Distribution-Specific Tasks

This file is loaded on demand by the **Linux distribution specific tasks**
primitive in `primitives.md` when `DISTRO = Debian`.

On Debian the UNAME format looks like `6.19.11+deb14-amd64`.

---

## Downloading debug and source packages

The various kernel packages are available from the download site located at
`http://http.us.debian.org/debian/pool/main/l/linux/`, which provides the
index of all available files. Filter these files to match the UNAME value (from
the "Key Elements" table) and the `amd64` architecture. Also filter out any
files with a `.udeb` file extension.

**Important — the debug package is always required for source mapping.** On
Debian 14 and later, the non-debug packages ship a stub `System.map` whose
first line reads:
```
ffffffffffffffff B The real System.map is in the linux-image-<uname>-dbg package
```
and a compressed `vmlinuz` with no ELF symbols. Neither is usable for
`addr2line` or `gdb`. The real `vmlinux` and `System.map` are only in the
`-dbg` package (named `linux-image-<uname>-dbg_<ver>_amd64.deb`).
Always include the `-dbg` package in the download set — it is large (~1 GB)
but cached in `oops-workdir/debian/debs/` so it is only fetched once per
kernel version.

**If the user says they don't have the debug package installed:** do not
treat this as a reason to skip. The package is always downloadable from the
Debian archive at no cost. Guide the user through the download steps below.
Do not mark VMLINUX as "not available" until you have actually attempted the
download and confirmed it failed (e.g. no network, insufficient disk space).
Without the vmlinux from the -dbg package, backtrace-to-source mapping is
not possible and the analysis will be significantly degraded.

Create a directory in the working space, `oops-workdir/debian/debs/` and
use that directory to download all matching files if they do not exist in
this directory yet (use this directory as a cache for future analysis).

**Disk space check — do this before downloading or extracting.** The `-dbg`
package alone is ~1 GB to download and expands to roughly 3 GB unpacked.
Check that the filesystem containing `oops-workdir/` has at least 3 GB free:
```bash
df -h oops-workdir/
```
If free space is below 3 GB, stop and tell the user how much space is
available and how much is needed, and ask them to free up space before
continuing.

## Extracting the packages

Create the directory `oops-workdir/debian/files/`.

If the `dpkg-deb` command is available, run the following command on each
downloaded `.deb` file:
```bash
dpkg-deb -xv <full path to the .deb file>  oops-workdir/debian/files
```

Then add a row to the "Key Elements" table for `BASEDIR`, and set it to
`oops-workdir/debian/files/`.

## vmlinux and System.map locations

The `-dbg` package installs the real `vmlinux` and `System.map` under:
```
BASEDIR/usr/lib/debug/boot/vmlinux-<UNAME>
BASEDIR/usr/lib/debug/boot/System.map-<UNAME>
```
Set `VMLINUX` in the "Key Elements" table to the `vmlinux-<UNAME>` path.

## Fetching kernel source

### Option A — Salsa git tree (preferred)

The Debian kernel team's git tree is hosted on Salsa. Checkout the
branch matching `DEBIAN_VER`:

```bash
# Clone once, then reuse:
git clone --depth=1 \
  https://salsa.debian.org/kernel-team/linux.git \
  -b debian/<DEBIAN_VER> \
  oops-workdir/debian/src/linux
```

Where `<DEBIAN_VER>` is e.g. `6.19.11-1`. If the repository already
exists in `oops-workdir/debian/src/linux`, update and checkout instead:

```bash
git -C oops-workdir/debian/src/linux remote update
git -C oops-workdir/debian/src/linux checkout debian/<DEBIAN_VER>
```

Set `SOURCEDIR` in the "Key Elements" table to
`oops-workdir/debian/src/linux`.

The Salsa tree also provides the canonical URL base for source code
links in the report. For a file at line N:
```
https://salsa.debian.org/kernel-team/linux/-/blob/debian/<DEBIAN_VER>/<file>#L<line>
```

### Option B — apt-get source (fallback)

If the Salsa checkout fails (network, missing branch, etc.), fall back
to `apt source`. `apt source` always extracts into the **current working
directory**, so it must be run from inside the target directory. Create
`oops-workdir/debian/src/` and run the command from there (replace
`<DEBIAN-VER>` with the value of the `DEBIAN-VER` field in the "Key
Elements" table):
```bash
mkdir -p oops-workdir/debian/src
cd oops-workdir/debian/src
apt-get source linux=<DEBIAN-VER>
```
Check if the tree already exists from prior runs and skip this extraction
for efficiency as needed.

This downloads and extracts the source into a subdirectory named
`linux-<base-version>` (e.g. `linux-6.19.11` for DEBIAN-VER `6.19.11-1`).
Set `SOURCEDIR` in the "Key Elements" table to the full path of that directory
(e.g. `oops-workdir/debian/src/linux-6.19.11`).

Note: source links in the report must use the Salsa URL pattern above;
`apt source` does not have an equivalent online URL.
