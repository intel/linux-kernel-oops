# Ubuntu — Pre-fetch Tasks

**Demand-load this file** when the fetcher agent detects `DISTRO = Ubuntu`
(UNAME matches `X.Y.Z-N-generic` and kernel header contains `-Ubuntu`).

This file covers only the **easy paths** that are mechanical enough for the
fetcher agent to handle reliably. Anything requiring Launchpad search,
user interaction, or source package extraction stays in the collector.

---

## Step 1 — Derive package version

Extract from the oops header line (e.g. `#29~24.04.1-Ubuntu`):

```
<rebuild>  = number after '#'       e.g. 29
<ubuntu-release> = number after '~' e.g. 24.04.1
```

Combined with UNAME `<kernel-base>-<abi>-generic` (e.g. `6.14.0-29-generic`):

```
package version = <kernel-base>-<abi>.<rebuild>~<ubuntu-release>
filename (amd64) = linux-image-unsigned-<kernel-base>-<abi>-generic-dbgsym_<package-version>_amd64.ddeb
```

**If the header has no `~`** (e.g. `#14-Ubuntu`): package version cannot be
derived here. Record `UBUNTU_DDEB: not derivable — collector handles` in
prefetch.md and skip to Step 3 (git tree), then stop.

## Step 2 — Disk space check

```bash
df -h oops-workdir/
```

The `-dbgsym` ddeb is ~1 GB to download and ~3 GB extracted. If free space
is below 3 GB, record `UBUNTU_DDEB: insufficient disk space (<N> GB free,
3 GB needed)` in prefetch.md and skip the download. The collector will
report this to the user.

## Step 3 — Derive Ubuntu series name

Map the `<ubuntu-release>` major.minor (e.g. `24.04`) to a series name:

| Release | Series  |
|---------|---------|
| 25.04   | plucky  |
| 24.10   | oracular|
| 24.04   | noble   |
| 23.10   | mantic  |
| 23.04   | lunar   |
| 22.04   | jammy   |
| 21.10   | impish  |
| 21.04   | hirsute |
| 20.10   | groovy  |
| 20.04   | focal   |
| 18.04   | bionic  |
| 16.04   | xenial  |

If the release does not appear in this table, record
`UBUNTU_SERIES: unknown (<release>)` and proceed to Step 4 (ddeb download
only; git checkout requires a known series name).

## Step 4 — Ubuntu git checkout (preferred source path)

This is the preferred way to get Ubuntu kernel source — it sets up
`oops-workdir/linux` directly and avoids the `apt-get source` extraction
step the collector would otherwise need.

**Requires**: series name from Step 3 and package version from Step 1.

Add the Ubuntu kernel git remote (using `ubuntu-<series>` to avoid clashes
if multiple series are ever needed):

```bash
git -C oops-workdir/linux remote add ubuntu-<series> \
    git://git.launchpad.net/~ubuntu-kernel/ubuntu/+source/linux/+git/<series>
```

If the remote already exists (`git remote get-url ubuntu-<series>` succeeds),
skip the `remote add`.

Fetch only the tag matching the package version (shallow fetch to keep it fast):

```bash
git -C oops-workdir/linux fetch ubuntu-<series> \
    Ubuntu-<package-version> --depth=1
git -C oops-workdir/linux checkout FETCH_HEAD
```

If the fetch fails (tag not found, network error), record
`SOURCEDIR: ubuntu git fetch failed` in prefetch.md and continue to Step 5
(ddeb download). The collector will fall back to `apt-get source`.

If the checkout succeeds:
- Record `SOURCEDIR: ready (ubuntu-<series> Ubuntu-<package-version>)` in
  prefetch.md
- Re-run semcode index on the checked-out tree:
  ```bash
  semcode-index -s oops-workdir/linux
  ```
- Record `SEMCODE_INDEX: refreshed (ubuntu-<series>)` in prefetch.md

## Step 5 — Download the ddeb

Skip this step if disk space was insufficient (Step 2 flagged it).

Check the cache first — skip download if already present:
```bash
ls oops-workdir/ubuntu/debs/<filename>
```

**Option 1 — ddebs.ubuntu.com** (most recent kernels):

```bash
# Find the subdirectory (linux/, linux-hwe-6.14/, etc.)
curl -s "http://ddebs.ubuntu.com/pool/main/l/" \
  | grep -o 'href="[^"]*"' | grep -i "linux"
# Then browse the matching subdirectory and download
wget -P oops-workdir/ubuntu/debs/ \
  "http://ddebs.ubuntu.com/pool/main/l/<subdir>/<filename>"
```

**Option 2 — Launchpad direct** (fallback, works for older kernels):

```bash
mkdir -p oops-workdir/ubuntu/debs/
wget -P oops-workdir/ubuntu/debs/ \
  "https://launchpad.net/ubuntu/+archive/primary/+files/<filename>"
```

If both options fail, record `UBUNTU_DDEB: download failed` in prefetch.md.
The collector will surface the error to the user.

On success, record `UBUNTU_DDEB: ready (oops-workdir/ubuntu/debs/<filename>)`
in prefetch.md.

> **Note — extraction is NOT done here.** The collector performs
> `dpkg-deb -x` or targeted extraction once it knows which files are needed
> (vmlinux, specific modules). The fetcher only ensures the .ddeb is cached.

---

## prefetch.md additions for Ubuntu

Add these rows to the Artifacts table in prefetch.md:

| Item | Status | Path / Value |
|------|--------|-------------|
| UBUNTU_PKG_VERSION | `<version>` / not derivable | — |
| UBUNTU_SERIES | `<series>` / unknown | — |
| UBUNTU_DDEB | ready / failed / not derivable / insufficient disk | oops-workdir/ubuntu/debs/<filename> |
