# Security Assessment

**Demand-load this file** when the Security Assessment step is reached in the
Deep Analysis flow (Paging Request, BUG/BUG_ON, and Panic crash types only).

The goal is to add an optional **Security Note** section to the final report.
**Only include the Security Note when confidence is high.** All other outcomes
produce no Security Note section — do not add a section that says "no security
impact", "not exploitable", "unlikely to be exploitable", "low severity", or
any other negative security statement — simply omit the section entirely.
When in doubt, omit.

The assessment must be run **after** the What-How-Where analysis and after the
upstream fix search ("Checking the git tree if the issue may already be fixed").

---

## Path A — Upstream fix is known

Use this path **only** when the **Where** section of the analysis has
independently and explicitly concluded that an upstream fix exists — for
example, a specific commit was found via `git log` / `git blame` / patch
review, and you are confident it addresses the root cause identified in the
What-How-Where analysis.

**Do not enter Path A solely because `fix_candidates` appears in the script
output.** `fix_candidates` is a heuristic that over-reports: it may surface
commits that are merely nearby in the git history. Only treat it as a fix if
the Where step already confirmed it.

Once the Where step has confirmed a fix, take its hash (or, if Where
concluded a fix without identifying an exact hash, fall back to the **first**
entry of `fix_candidates` as a candidate — but re-verify it before using it).
Search lore for a CVE announcement:

```
https://lore.kernel.org/all/?q=%22<first-12-chars-of-fix-hash>%22+AND+%22CVE%22
```

Fetch that URL and look for a result line matching the pattern:
```
<N>. CVE-<year>-<number>: <subject>
```
(where `<N>` is a small integer, `<year>` is a 4-digit year, `<number>` is a
sequence of digits).

**If a CVE is found:**

1. Fetch the CVE announcement article linked in the result (URL pattern:
   `https://lore.kernel.org/all/<message-id>/`). Verify it matches by
   checking:
   - The "Affected files" section references the same file(s) as this crash.
   - The "Description" section is consistent with the root cause identified in
     the What-How-Where analysis.

2. If verification passes, add to the report:

   ```
   ## Security note

   This issue has been assigned **<CVE-ID>** by the Linux kernel CVE team.
   See the [CVE announcement](<lore-url>) for the full record.
   ```

   Also add a `CVE` row to the **Key Elements** table:
   ```
   | CVE | <CVE-ID> | [<CVE-ID>](https://cve.org/CVERecord/?id=<CVE-ID>) |
   ```

3. If verification fails (files don't match, or description is for a different
   bug): do not add a Security Note. Note in the report body that a CVE was
   found but could not be confirmed as matching this crash.

**If no CVE is found:** proceed to Path B.

---

## Path B — No upstream fix, or no CVE found via Path A

Perform the following five-step structured analysis. Step 1 may
short-circuit to a named outcome; otherwise continue through Steps 2–5
and use the conclusion table at the end to determine whether a Security
Note is added.

### Step 1 — Standard security type

Check whether the crash matches a well-known vulnerability class **before**
doing any other classification. If it does, the outcome is that class name
and Steps 2–5 plus the conclusion table are **skipped entirely**.

**Use After Free (UAF)** — the crash is caused by accessing memory after
it has been freed. Indicators:
- KASAN report contains `slab-use-after-free` or `use-after-free`
- The crash site dereferences a pointer that was previously passed to
  `kfree()`, `kmem_cache_free()`, or a `*_put()` / `*_free()` release
  function earlier in the call chain
- The object's refcount was already zero (or the object was marked dead)
  at the point of access

If the crash matches UAF, add this Security Note and stop here:

```
## Security note

This crash is a **Use After Free (UAF)**. The Linux Kernel CVE team is
likely to assign a CVE to this issue (no upstream fix identified).
```

If no standard type matches, proceed to Step 2.

### Step 2 — Privileged vs Unprivileged vs Other

Classify who can trigger the key elements of the issue.

**Unprivileged** (highest severity) — normal (non-root) userspace can trigger it:
- Normal general system calls (not ioctl)
- Generic file system operations on normal files (not `/proc` or `/sys`)

**Privileged** — only root-level processes can trigger it:
- Writing to files in `/proc` or `/sys`
- `ioctl` system calls into drivers
- Operating on files in `/dev`
- Creating an unusual or unexpected system configuration

**Other** — all key elements come from hardware sources (BIOS, interrupts) or
happen early at boot, OR you have no strong confidence in either of the above.
When in doubt, pick Other.

### Step 3 — User vs Application

**User** — any of these apply:
- Normal Linux shell commands can trigger the issue
- The issue is due to an unexpected or bad configuration
- The issue involves a physical operation (e.g. inserting/removing USB)

**Application** — otherwise. When in doubt, pick Application.

### Step 4 — Regular vs Unusual

**Unusual** — very special or uncommon configurations/arguments are required to
trigger the issue.

**Regular** — typical conditions. When in doubt, pick Regular.

### Step 5 — Crash vs Other

**Crash** — null pointer dereference, BUG(), BUG_ON(), page fault, or other
fatal crashes.

**Other** — WARNING (system continues after printing the message).

### Conclusion table

Process from top to bottom; stop at the first matching row.
`*` = wildcard (matches any value).

| Step 2       | Step 3      | Step 4   | Step 5 | Outcome |
|--------------|-------------|----------|--------|---------|
| Unprivileged | User        | *        | Crash  | Report: Unprivileged User |
| Unprivileged | Application | *        | Crash  | Report: Unprivileged Application |
| Privileged   | Application | Regular  | Crash  | Report: Privileged Application |
| *            | *           | *        | *      | Omit the Security Note section entirely — no negative statement |

**If an outcome from the first three rows is reached**, add to the report:

```
## Security note

The Linux Kernel CVE team is likely to assign a CVE to this issue
(**<outcome classification>** crash, no upstream fix identified).
```

---

## Language in other report sections

When the security outcome is **Use After Free**, **Unprivileged User**,
**Unprivileged Application**, or **Privileged Application**, use that
phrasing consistently in:
- The **Analysis, conclusions and recommendations** section
- Any patch email (`patch-email.txt`) generated for this issue — use the
  phrasing in the patch subject or cover-letter body to signal severity to
  reviewers and the stable team
