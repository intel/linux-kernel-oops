# Debian — Pre-fetch Tasks

**Demand-load this file** when the fetcher agent detects `DISTRO = Debian`
(UNAME matches `X.Y.Z+debN-amd64` pattern or kernel header contains `-Debian`
or `Debian`).

This file covers only the **easy paths** that are mechanical enough for the
fetcher agent to handle reliably. Source package extraction and `apt-get source`
stay in the collector.

---

## Step 1 — Disk space check

```bash
df -h oops-workdir/
```

The `-dbg` package is ~1 GB to download and ~3 GB extracted. If free space
is below 3 GB, record `DEBIAN_DBG_DEB: insufficient disk space (<N> GB free,
3 GB needed)` in prefetch.md and stop. The collector will report this to
the user.

## Step 2 — Find the package in the Debian pool

Browse the Debian pool index filtered to the kernel packages:

```bash
curl -s "http://http.us.debian.org/debian/pool/main/l/linux/" \
  | grep -o 'href="[^"]*"' \
  | grep "amd64" \
  | grep -v "\.udeb"
```

From the listing, find the **`-dbg`** package whose name contains the UNAME
string (e.g. `linux-image-6.19.11+deb14-amd64-dbg_6.19.11-1_amd64.deb`
for UNAME `6.19.11+deb14-amd64`).

Extract the full filename and the package version (`DEBIAN_VER`) from it:
- Filename pattern: `linux-image-<uname>-dbg_<debian-ver>_amd64.deb`
- `DEBIAN_VER` = the `<debian-ver>` portion (e.g. `6.19.11-1`)

If no matching `-dbg` package is found in the pool listing:
- Record `DEBIAN_DBG_DEB: not found in pool` and `DEBIAN_VER: not found`
  in prefetch.md and stop. The collector will handle this failure.

## Step 3 — Download the `-dbg` package

Check the cache first — skip download if already present:

```bash
ls oops-workdir/debian/debs/<filename>
```

If not cached, download it:

```bash
mkdir -p oops-workdir/debian/debs/
wget -P oops-workdir/debian/debs/ \
  "http://http.us.debian.org/debian/pool/main/l/linux/<filename>"
```

Verify the downloaded file is non-empty. If the download fails, record
`DEBIAN_DBG_DEB: download failed (<reason>)` in prefetch.md and stop.

On success, record the path in prefetch.md.

> **Note — extraction is NOT done here.** The collector runs `dpkg-deb -xv`
> once it is ready to map backtrace entries to source. The fetcher only
> ensures the `.deb` is cached.

## Step 4 — Salsa git checkout (sets SOURCEDIR)

Clone or update the Debian kernel Salsa tree to the branch matching
`DEBIAN_VER`. This sets `SOURCEDIR` so the collector can do source
mapping without running `apt-get source`.

```bash
SALSA=https://salsa.debian.org/kernel-team/linux.git
SRCDIR=oops-workdir/debian/src/linux

if [ -d "$SRCDIR/.git" ]; then
  git -C "$SRCDIR" remote update --prune
  git -C "$SRCDIR" checkout debian/<DEBIAN_VER>
else
  git clone --depth=1 "$SALSA" -b debian/<DEBIAN_VER> "$SRCDIR"
fi
```

On success, record `SOURCEDIR: oops-workdir/debian/src/linux` in
prefetch.md.

If the checkout fails (network issue, branch not found), record
`SOURCEDIR: not available (Salsa checkout failed)` — the collector
will fall back to `apt-get source`.

---

## prefetch.md additions for Debian

Add these rows to the Artifacts table in prefetch.md:

| Item | Status | Path / Value |
|------|--------|-------------|
| DEBIAN_VER | `<version>` / not found | e.g. `6.19.11-1` |
| DEBIAN_DBG_DEB | ready / failed / not found / insufficient disk | oops-workdir/debian/debs/<filename> |
| SOURCEDIR | ready / not available | oops-workdir/debian/src/linux |
