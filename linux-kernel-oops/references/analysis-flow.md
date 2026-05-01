# Deep Analysis Flow

This file contains Phase 3 — the analyst agent's procedure. It assumes
Phase 2 (Basic Data Collection) is fully complete. All structured data,
debug symbols, and source code should already be in hand.

**Time budget: 20 minutes**, starting fresh when the analyst agent launches
(independent of Phase 2 time). **Run `date` now to record your start time
and calculate your hard deadline.** Stop when the budget is exhausted, even if
the analysis is incomplete. Before stopping, write up whatever has been
established so far and clearly mark any open questions with
*"(analysis budget reached — incomplete)"*.

Now perform the "What - How - Where" analysis protocol with the information
that was gathered in Phase 2. Use any primitives that are still useful based
on what the analysis reveals. It is ok if not all steps can be done
exhaustively, a kernel oops report is often partial and limited in
information. However, be clear on the distinction between "Most likely based
on an assumption" and "Complete fact based on full analysis" in any
reporting done.

Most of this section is worded in the context of an example of a NULL
dereference, but the concepts apply equally to other crash types.

At the end of the "What - How - Where" analysis, add a section to the
report output that has these three elements as subsections, and include your
analysis and recommendation in the appropriate subsection.


## Blame layer heuristic

Before diving into the analysis, orient yourself with this prior: bugs are
far more common in drivers than in subsystems, and far more common in
subsystems than in the kernel core.

**Practical implications:**

- **Crash in a driver** (e.g. `drivers/i2c/i2c-dev.c`): the primary suspect
  is a bug in the driver itself. The subsystem is a secondary suspect only
  if the driver is doing everything correctly and the subsystem API contract
  is unclear or violated. Kernel core (VFS, scheduler, memory) is almost
  never the root cause.

- **Crash in a subsystem** (e.g. `drivers/i2c/i2c-core-base.c`,
  `net/ipv4/`, `fs/`): the primary suspect is the subsystem. Caller
  (driver) misuse is a common secondary cause — check whether the caller
  violated a precondition. Kernel core involvement is a last resort
  hypothesis.

- **Crash in kernel core** (e.g. `mm/`, `kernel/`, `lib/`): the core code
  is likely correct; trace back up the backtrace to find which subsystem
  or driver passed bad state in.

When writing the How and Where sections, let this heuristic guide where you
spend investigation time and where you propose the fix.


## What step
The "What" step is about knowing what happened to cause the crash, for example 
"in this line of code in this function, the pointer F was NULL so dereferencing caused a
crash". 

The Basic Data Collection flow should have generated enough
information to describe the What, by showing the source code
of the crashing function (if the top of the backtrace shows address 0x0,
use the next entry instead) using the **Reporting a source code function**
primitive — read [reporting.md](reporting.md) for the full formatting rules.
Two requirements from that primitive are critical and must not
be skipped:

- **Clickable URL** — place a Markdown link to the online git tree
  (kernel.org stable tree, GitLab CKI for Fedora, Launchpad for Ubuntu,
  etc.) immediately before every source code block.
- **Line number prefix** — every line of source must be prefixed with its
  actual file line number, right-aligned. This is mandatory. Exception:
  agent-added annotation comments (e.g. `// ← RBX = NULL`) and `...`
  elision lines do not get line numbers.

Annotate the source with information deduced from the oops.
When a struct is involved in the crash, look up the definition of the
struct.

Sometimes it is possible to even gather the value of local variables based
on the registers in the oops; try this for any variable that is essential to
the cause of the crash (the actual dereference, but also potentially any if
statements that were there to protect the dereference)

⛔ **CHECKPOINT — update the report now.** Add (or update) the **What**
subsection in the report file immediately. Run `date` and check elapsed time
against your budget. If over budget: stop here, mark remaining sections
*"(analysis budget reached — incomplete)"*, and skip to the Analysis reply
email step. Otherwise proceed to the How step.


## How step

The "How" step's objective is to trace through the source code to find out
HOW the condition that caused the crash could have happened.

There are three cases, split into subsections below.

### Positive How

If you can explicitly trace the assignment of the NULL value to the variable
that later gets dereferenced, this is a "Positive How"; an
explicit action directly caused the NULL to appear.

As part of tracing the "How" step, repeat the "How" question at least once:

Q1: How did the NULL value get to the crash site
A1: This field became NULL because at line 54 of file.c it got assigned to the return value of function get_foo();
⛔ **Update the report now** — write the Q1/A1 finding to the How subsection before continuing.

Q2: How did the function get_foo() end up returning NULL?
A2: get_foo() only returns NULL if <some global condition happens>
⛔ **Update the report now** — write the Q2/A2 finding to the How subsection before continuing.
...

Some analysis ends up needing three or four rounds of the "How" question to
get to a plausible root cause. **After each round, update the report and check
the time before starting the next round.**

### Negative How

Sometimes the "NULL" value originates from the original allocation of the
data, and nothing assigned a real value to the field in question.
The right question to chase at that point is "How did this field NOT get a
value assigned?"

This will generally require looking at prevailing code patterns for this
field and find the places where the field is normally assigned a value.
Once a normal pattern that sets the value is found, the key question centers
around why these normal patterns did NOT trigger for the case in question.

Sometimes the answer lies in global conditions or parameters passed
incorrectly, but race conditions during initialization should always be considered.

### Unknowable How

The crash information may not have sufficient information to trace down
either case — at which point there is an "Unknowable How" — report to the
user a brief summary of what was analysed and what could not be determined.

⛔ **CHECKPOINT — update the report now.** Add (or update) the **How**
subsection in the report file immediately. Run `date` and check elapsed time
against your budget. If over budget: stop here, mark remaining sections
*"(analysis budget reached — incomplete)"*, and skip to the Analysis reply
email step. Otherwise proceed to the Where step.


## Where step

The last step in the "What-How-Where" protocol is about where the fix needs
to go.
The default option, when all else fails, is to add a check at the site of
the What, for example a NULL pointer check.

As part of finding a good place for a fix, consider how the error can be
handled at this level.

However, based on the How analysis, several better options may have been
found. Examples of such cases are

- A function put NULL in a field during initialization as a failure
    condition but the code did not catch that and registered/continued with
    the initialization anyway. The correct fix is to catch the failure condition
    during init. 
- The "What" code gets called repeatedly (say in a loop); putting the NULL
    check inside the loop is not great as each iteration of the loop will
    individually fail. Better to uplevel the check so that the loop does not
    happen in the failure case

If relevant, write a proposed fix as a **rough** unified diff. Save it to
`report.patch` in the same directory as report.md — this is the handoff
file for the patch agent. Do **not** run the patch formatting steps
yourself; that is the patch agent's job. Specifically, do NOT:
- Run `git apply --check` on the diff
- Add `Signed-off-by`, `Fixes:`, `Reported-by`, or other trailers
- Write `patch-email.txt`, `git-send-email.sh`, or any send script for the patch
- Format the diff as a git format-patch email

The rough diff only needs to be correct in terms of logic and context lines —
the patch agent will validate, clean up, and format it for LKML.

Include the rough diff inline in the **Where** section of report.md as
well (inside a fenced `diff` block) so the report is self-contained.

Note in report.md the exact base commit or tag the diff was written
against (e.g. `PATCH_BASE: v6.14` or `PATCH_BASE: 6596a02b2078`). The
patch agent needs this to validate cleanly.

**Diff review — check before writing `report.patch`.**
Before saving the diff, review it for correctness issues that would make
the patch unsuitable for submission:

- **Resource leaks**: does every new allocation or reference-count increment
  have a matching free / put on all exit paths, including error paths?
  Trace every `goto`, `return`, and early-exit after the new code.
- **Lock imbalance**: does every new `lock` / `spin_lock` / `mutex_lock`
  have a matching unlock on all paths, including error paths?
- **NULL / uninitialized dereference introduced**: does the fix itself
  dereference a pointer that could be NULL or unset at that point?
- **Error path coverage**: if the fix adds a new operation that can fail,
  is the failure handled and propagated correctly?
- **Side effects on callers**: does the fix change a function's return value,
  memory ownership contract, or locking preconditions in a way that breaks
  existing callers not covered by the patch?

If any of these issues are found, **do not write `report.patch`**. Instead,
note the problem in report.md under **Where** (e.g. *"Fix concept identified
but suppressed: proposed change leaks `skb` on the error path at line 423"*)
and leave `PATCH_BASE` unset. The patch agent will not run.

If the review passes, write `report.patch` and set `PATCH_BASE`.

⛔ **CHECKPOINT — update the report now.** Add (or update) the **Where**
subsection (and patch file if produced) in the report file immediately.
Run `date` and check elapsed time against your budget. If over budget: stop
here, mark remaining sections *"(analysis budget reached — incomplete)"*, and
skip to the Analysis reply email step. Otherwise proceed to the Security
assessment or Bug Introduction steps.


## Security assessment

**Run this step for Paging Request, BUG/BUG_ON, and Panic crashes only.**
Skip entirely for WARNING crashes.

Read [security.md](security.md) and follow the Security Assessment procedure.
It must run **after** the Where step and the upstream fix search are complete.
Only add a `## Security note` section to the report if the procedure yields a
high-confidence outcome; otherwise omit the section entirely.


## Analysis reply email

Read [decode-email.md](decode-email.md) and follow the procedure to generate
`analysis-email.txt` and `git-send-analysis.sh` in the archive directory.

**Skip this step if either of these conditions is not met:**
- A Message-ID (MSGID) is not available for the original report.
- The analysis was not high-confidence (source code not found for the exact
  kernel version, or discrepancies were found during analysis).

## Bug introduction analysis

Run this step after completing the **Where** step. **Skip this step entirely
if the How analysis was inconclusive ("Unknowable How").**

**Run `date` before starting this step.** If less than 3 minutes remain in
your budget, skip this step entirely and proceed to the Analysis reply email.

The goal is to identify the commit that *changed* existing code to introduce
the bug — not the commit that first created the file.

### Step 1 — Determine the blame version

Use the kernel version tag from `UNAME_RELEASE` (e.g. `v6.14`). If that
exact tag is not present in the git tree (e.g. distro or custom builds),
fall back to the nearest upstream tag at or before the reported version:

```bash
git -C oops-workdir/linux tag --sort=-version:refname | grep "^v[0-9]" | head -20
```

Pick the highest tag that is ≤ the reported kernel version. Note in the
report that the blame is approximate if a fallback was used.

### Step 2 — Run `git blame` on root-cause files

Run `git blame -w <tag> -- <file>` **only on the file(s) identified as the
root cause in the How analysis** (not all backtrace files).

**`git blame` sub-budget: stop after 5 `git blame` calls.** Each blame call
also counts against the overall 20-lookup budget (see Step 3).

From the blame output, extract only the lines of code that the How analysis
identified as implicated (the root-cause function body, the buggy assignment,
the racing code path, etc.). Ignore lines in unrelated functions.

Collect the unique commit hashes from those lines.

### Step 3 — Inspect each candidate commit

**Overall budget: stop after 20 total git operations** (blame calls +
`git show` + `git log` calls combined). Stop early if a strong candidate
is found.

For each unique hash from Step 2, run `git show --stat <hash>` and inspect
the commit subject and diff. Exclude a commit if it matches **any** of:

- The commit **creates a whole new driver or subsystem file** (e.g. the diff
  shows only `+` lines and the file did not previously exist). Adding new
  functionality *inside* an existing file is **not** grounds for exclusion —
  such commits can and do introduce bugs.
- The commit subject contains any of: `rename`, `move`, `reorganize`,
  `refactor`, `cleanup`, `treewide`, `coccinelle` — these are structural
  changes that are very unlikely to introduce a logic bug.

### Step 4 — Group and rank candidates

- **Group** commits that were authored within two weeks of each other and
  touch the same file(s) into a single candidate series.
- **Prefer** the most recent candidate (by author date) when multiple
  candidates remain after grouping.
- If multiple independent candidates exist after grouping, report all of
  them but call out the most recent as the primary suspect.

### Step 5 — Report and optionally re-examine

If a strong candidate (or series) is found:

1. Record it in the report under the **Bug Introduction** section (see
   template). If the candidate commit is a whole new driver or subsystem
   introduction (all-new file that was excluded by the filter but surfaced
   as the only commit touching those lines), do **not** silently drop it —
   instead report: *"The bug has been present since the introduction of
   `<driver/subsystem name>` in commit [`<hash>`](…) (<date>)."* This is
   still useful information even though there is no earlier "change" commit
   to point to.
2. Add an `INTRODUCED-BY` row to the **Key Elements** table in the report
   with the full commit hash (as a Markdown link) and the commit subject.
   If it is a series, list the primary commit hash.
3. **Re-examine the What-How-Where analysis once** with this new information
   — it may sharpen the root cause or suggest a better fix location. Do not
   re-run the bug introduction step again after this re-examination.

If no candidate survives the filters, or the budget is exhausted, state
"Bug introduction commit not identified within search budget" in the report.

All git hashes in this section must follow the same Markdown link rules as
the fix-search section — every occurrence must be a link.

⛔ **CHECKPOINT — update the report now.** Add (or update) the
**Bug Introduction** section and the `INTRODUCED-BY` Key Elements row in
the report file immediately. Do not proceed to the fix search until the
file is saved.


## A note on IRQ context
If the crash happens in interrupt context, it is often useful to:
- locate the source code where the interrupt handler was registered for device interrupts —
    find the relevant `request_irq` call (or equivalent functions) and check
    whether all fields are initialized properly prior to that call.
- locate the source code where a timer was registered for timer interrupts
    (add_timer, mod_timer and related APIs)



## Checking the git tree if the issue may already be fixed
If SOURCEDIR contains a git tree, search the git history for fixes already
applied to the upstream tree that would resolve this oops. This section
describes minimum checks to be done; the agent has full access and control
of the git tree and should consider what other analysis could be useful.

When reporting git hash values to the user, format them as Markdown links.
**Every occurrence** of a git hash — first mention, re-mentions, tables, bullet lists — must be
a Markdown link; never use a bare hash or plain `code` span.
The link URL follows this pattern (the `?id=` query parameter takes the full commit hash):
```
https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/commit/?id=b731aca06387b195058a9f6449a03b62efa1bd10
```
Use the short hash (first 12 characters) as the link text, for example:
`[b731aca06387](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/commit/?id=b731aca06387b195058a9f6449a03b62efa1bd10)`

**Critical:** search the files identified during the **How** analysis — NOT
only the crash-site file. The fix is often in the file containing the root-cause
function, which may be a completely different file from where the crash assertion
fires. For example, an assertion in `mm/filemap.c` may be fixed by a commit that
changes `mm/huge_memory.c`.

The `oops-workdir/linux` tree is for the agent's exclusive use — HEAD can be
freely moved. After checking out the UNAME tag for source reading, HEAD will
typically *be* that tag, making the range `<uname_tag>..HEAD` empty and
returning no results. Always use `--all ^<uname_tag>` instead, which searches
every ref (branches and tags across all remotes) and excludes commits already
present in the UNAME version:

```bash
# Fast keyword grep — function name, struct name, or error string:
git -C oops-workdir/linux log --all --oneline \
    ^<uname_tag> \
    --grep="<root_cause_function>"

# File-history search — list all commits touching the root-cause source file
# that are NOT already in the UNAME version (use a specific remote branch to
# avoid scanning every tag, which is slow):
git -C oops-workdir/linux log --oneline \
    ^<uname_tag> origin/master \
    -- <root_cause_file>
```

**Also check linux-next.** Even when a fix is not yet in Linus' tree it may
already be queued in linux-next. After searching `origin/master`, repeat the
file-history and keyword searches against `linux-next/master`:

```bash
# Keyword search in linux-next:
git -C oops-workdir/linux log --oneline \
    ^<uname_tag> linux-next/master \
    --grep="<root_cause_function>"

# File-history in linux-next:
git -C oops-workdir/linux log --oneline \
    ^<uname_tag> linux-next/master \
    -- <root_cause_file>
```

If the `linux-next` remote is not present in the tree (check with
`git -C oops-workdir/linux remote get-url linux-next 2>/dev/null`), add and
fetch it before searching:

```bash
git -C oops-workdir/linux remote add linux-next \
    https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git
git -C oops-workdir/linux fetch linux-next master
```

A fix found only in linux-next (not yet in `origin/master`) should be reported
as **"queued in linux-next"** in the Key Elements table and in the Where
section, with the commit hash, author, date, and title. Use the linux-next
cgit URL for hash links:
```
https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git/commit/?id=<full_hash>
```

**Search budget: stop after 15 git searches total** (counting each `git log`
or `git show` call across both remotes). If no credible fix has been found by
then, report that no upstream fix was identified within the search budget and
move on. Stop earlier if a credible fix is found — there is no need to exhaust
the budget.
If `origin/master` is not available, substitute the appropriate remote branch
(`fedora/master`, `linus/master`, or similar — check `git remote -v`).

Review candidate commits for relevance. If a commit credibly fixes the identified
root cause and is not yet in the affected kernel version, it becomes the preferred
solution — report the commit hash, author, date, and title, and note whether a
stable backport exists.

**If a related fix is found but does not appear to cover this crash:**
Read the commit's patch (e.g. `git show <hash>`) and identify its fix pattern —
what specific code path, data structure field, or invariant it repairs. Then
correlate that pattern against the data already collected in the What and How
analysis:

- Does the fix address the same function or the same field that appears in the
  backtrace or register dump?
- Does the fix cover a different call site that exhibits the same root cause
  (e.g. the wrong free helper called in handler A, while this crash is in handler B)?
- Does the commit message reference a parent commit that changed shared
  semantics (e.g. a refactor that introduced a new invariant), suggesting
  additional call sites may still be affected?

From this, draw one of three conclusions:

1. **Partial fix — missed case:** The fix addresses the same root cause but
   covers only a subset of the affected code paths. This crash represents a
   remaining instance. Note which code path was missed and why. Consider
   proposing in the "Where" section a follow-on fix that extends the original
   patch to cover this remaining code path.
2. **Different root cause — same symptom:** The fix addresses a superficially
   similar bug but via a different mechanism. The two bugs share a symptom
   (same crash site or same error type) but have independent root causes.
   Note both bugs distinctly in the Where section.
3. **Fix is sufficient — crash predates it:** The fix does cover this crash path,
   but the affected kernel version predates the fix. Recommend updating to a
   version that includes the fix or to backport the specific fix.

⛔ **CHECKPOINT — update the report now.** Add (or update) the upstream fix
information (`FIXED-BY` Key Elements row and fix details) in the report file
immediately. Do not proceed to the Analysis reply email step until the file
is saved.

## Phase 3 complete — update the report

After all Phase 3 steps are finished (What/How/Where, security assessment,
analysis reply email, bug introduction analysis), **overwrite the report
file** saved at the end of Phase 2 with the final version:

- Remove the `⏳ **Analysis in progress**` banner.
- Add the **What / How / Where** section (with all subsections).
- Add the **Security note** section if the security assessment produced a
  high-confidence outcome.
- The Backtrace, Key Elements, source code listings, and all other Phase 2
  sections remain in place — update any cells (e.g. Source Location links)
  that can now be filled in more precisely.
- Do **not** create a second archive entry; overwrite the same
  `report.md` (and regenerate `report.html` if it was created in Phase 2).
- After saving, notify the user: *"Phase 3 complete — report updated at
  `<path>`."*
