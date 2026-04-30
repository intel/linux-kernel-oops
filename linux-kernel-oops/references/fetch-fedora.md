# Fedora — Pre-fetch Tasks

**Demand-load this file** when the fetcher agent detects `DISTRO = Fedora`
(UNAME matches `X.Y.Z-N.fcNN.x86_64` pattern).

This file covers only the **easy paths** that are mechanical enough for the
fetcher agent to handle reliably. RPM extraction and companion `.ko` retrieval
stay in the collector.

---

## Step 1 — Parse UNAME into components

From UNAME (e.g. `6.17.7-300.fc43.x86_64`), extract:

| Field | Example | How to derive |
|-------|---------|---------------|
| `FEDORA_VERSION` | `6.17.7` | everything before the first `-` |
| `FEDORA_RELEASE` | `300.fc43` | everything between the first `-` and the last `.` |
| `FEDORA_ARCH` | `x86_64` | everything after the last `.` |
| `FEDORA_DISTRO_VER` | `43` | digits after `fc` in the release field |

Record these in prefetch.md — the collector uses them to locate extracted files.

## Step 2 — Disk space check

```bash
df -h oops-workdir/
```

The `kernel-debuginfo` RPM is ~1–2 GB to download and ~3–4 GB extracted.
If free space is below 4 GB, record
`FEDORA_DEBUGINFO_RPM: insufficient disk space (<N> GB free, 4 GB needed)`
in prefetch.md and stop. The collector will report this to the user.

## Step 3 — Download the `kernel-debuginfo` RPM

Check the cache first — skip if already present:

```bash
ls oops-workdir/fedora/rpms/kernel-debuginfo-<FEDORA_VERSION>-<FEDORA_RELEASE>.<FEDORA_ARCH>.rpm
```

The Koji package server URL is directly derivable from the UNAME components —
no index browsing is needed:

```bash
mkdir -p oops-workdir/fedora/rpms/
curl -L -o oops-workdir/fedora/rpms/kernel-debuginfo-<FEDORA_VERSION>-<FEDORA_RELEASE>.<FEDORA_ARCH>.rpm \
  "https://kojipkgs.fedoraproject.org/packages/kernel/<FEDORA_VERSION>/<FEDORA_RELEASE>/<FEDORA_ARCH>/kernel-debuginfo-<FEDORA_VERSION>-<FEDORA_RELEASE>.<FEDORA_ARCH>.rpm"
```

If Koji returns a 404 (kernel archived), retry with the archive mirror:

```bash
curl -L -o oops-workdir/fedora/rpms/kernel-debuginfo-<FEDORA_VERSION>-<FEDORA_RELEASE>.<FEDORA_ARCH>.rpm \
  "https://dl.fedoraproject.org/pub/archive/fedora/linux/updates/<FEDORA_DISTRO_VER>/Everything/<FEDORA_ARCH>/debug/Packages/k/kernel-debuginfo-<FEDORA_VERSION>-<FEDORA_RELEASE>.<FEDORA_ARCH>.rpm"
```

If both fail, record `FEDORA_DEBUGINFO_RPM: download failed (<reason>)` in
prefetch.md and continue — do not abort.

Verify the downloaded file is non-empty. On success, record the path.

> **Note — extraction is NOT done here.** The collector runs
> `rpm2cpio ... | cpio -i -d -u` to populate `BASEDIR` and locate
> `vmlinux` and `.ko.debug` files. The fetcher only ensures the RPM is cached.

> **Note — `kernel-modules` RPM is NOT downloaded here.** The companion `.ko`
> for disassembly is only needed when entry 0 in the backtrace is inside a
> module, which is not known until the backtrace has been parsed. The collector
> downloads it on demand.

## Step 4 — Set up the Fedora kernel source tree

Fedora kernel sources are available via git from the CKI project at
`https://gitlab.com/cki-project/kernel-ark`.

### 4a — Derive the git tag

Strip the `.fc<N>.x86_64` suffix from the UNAME, then construct the candidate
tag:

```
kernel-<FEDORA_VERSION>-<build>
```

where `<build>` is the numeric prefix of `FEDORA_RELEASE` before `.fc<N>`
(e.g. `300.fc43` → `300`). So UNAME `6.17.7-300.fc43.x86_64` → try tag
`kernel-6.17.7-300` first.

**Important:** The RPM build number in the UNAME does not always match the
CKI tag build number. If the exact tag is absent, query the GitLab API:

```bash
curl -s "https://gitlab.com/api/v4/projects/cki-project%2Fkernel-ark/repository/tags?search=kernel-<FEDORA_VERSION>&per_page=20" \
  | python3 -c "import json,sys; [print(t['name']) for t in json.load(sys.stdin)]"
```

Use the tag that matches `FEDORA_VERSION` (e.g. `kernel-6.17.7-0` if
`kernel-6.17.7-300` is absent). Record the resolved tag as `FEDORA_TAG`.

If no matching tag is found at all, record `FEDORA_TAG: not found` and
`SOURCEDIR: failed` in prefetch.md and skip 4b.

### 4b — Add remote, fetch tag, and check out

If a git tree already exists at `oops-workdir/linux`, check whether the
`fedora` remote and the needed tag are already present:

```bash
git -C oops-workdir/linux remote get-url fedora 2>/dev/null \
  || git -C oops-workdir/linux remote add fedora https://gitlab.com/cki-project/kernel-ark
```

Check if the tag is already fetched — only fetch if missing:

```bash
git -C oops-workdir/linux rev-parse --verify "refs/tags/<FEDORA_TAG>" 2>/dev/null \
  || git -C oops-workdir/linux fetch fedora "refs/tags/<FEDORA_TAG>:refs/tags/<FEDORA_TAG>"
```

If no tree exists yet, clone from the CKI remote. Check for a local reference
repo to speed up the clone:

```bash
for candidate in ~/linux ~/git/linux ~/src/linux; do
    [ -d "$candidate/.git" ] || [ -d "$candidate/objects" ] && REF=$candidate && break
done

if [ -n "$REF" ]; then
    git clone --reference-if-able "$REF" \
        https://gitlab.com/cki-project/kernel-ark oops-workdir/linux
else
    git clone https://gitlab.com/cki-project/kernel-ark oops-workdir/linux
fi
```

Note in prefetch.md whether a reference repo was used. Then fetch the tag as
above.

Then check out:

```bash
git -C oops-workdir/linux checkout <FEDORA_TAG>
```

On success, `SOURCEDIR = oops-workdir/linux`. Note the result in prefetch.md.

---

## prefetch.md additions for Fedora

Add these rows to the Artifacts table in prefetch.md:

| Item | Status | Path / Value |
|------|--------|-------------|
| FEDORA_VERSION | `<version>` | e.g. `6.17.7` |
| FEDORA_RELEASE | `<release>` | e.g. `300.fc43` |
| FEDORA_ARCH | `<arch>` | e.g. `x86_64` |
| FEDORA_TAG | `<tag>` / not found | e.g. `kernel-6.17.7-300` |
| FEDORA_DEBUGINFO_RPM | ready / failed / insufficient disk | oops-workdir/fedora/rpms/kernel-debuginfo-... |
| SOURCEDIR | ready / failed | oops-workdir/linux |
