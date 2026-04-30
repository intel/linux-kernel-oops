# Lockdep — Locks Held Extraction

**Demand-load this file** when the oops report contains a "locks held" block.

When a kernel crash occurs while locks are held, the kernel prints a lock list
before the backtrace. This information is useful for understanding what
synchronisation invariants were active at crash time — for example, whether an
RCU read-side critical section was open, or which inode/filesystem write locks
were held when a sleeping function was called.

---

## Detecting the locks-held block

Look for one of these patterns in the report:

```
N locks held by <process>/<pid>:
```

or, from a separate WARNING after the main crash:

```
<process>/<pid> is leaving the kernel with locks still held!
N lock held by <process>/<pid>:
```

If neither appears, skip this step — there is no lock information to extract.

---

## Parsing format

Each lock entry looks like:

```
 #N: <address> (<lock-name>){<state-flags>}-{<hardirq:softirq>}, at: <function>+<offset>/<size> <file:line>
```

Example from a syzbot BUG report:

```
2 locks held by rm/5904:
 #0: ffff88802b0d0410 (sb_writers#5){.+.+}-{0:0}, at: filename_unlinkat+0x1ad/0x730 fs/namei.c:5545
 #1: ffffffff8e7e5260 (rcu_read_lock){....}-{1:3}, at: rcu_lock_acquire.constprop.0+0x7/0x30 include/linux/rcupdate.h:300
```

Field breakdown:

| Field | Meaning |
|---|---|
| `#N` | Lock index (0-based) |
| `<address>` | Kernel address of the lock object |
| `(<lock-name>)` | Lock class name (e.g. `sb_writers#5`, `rcu_read_lock`) |
| `{<state-flags>}` | Lock state at crash time: read/write held, hardirq/softirq enabled/disabled |
| `-{<hi>:<si>}` | Lock class type/nesting depth (hardirq:softirq count) |
| `at: <function>+<offset>/<size>` | The function that **acquired** the lock, and at what offset |
| `<file:line>` | Source annotation for the acquisition site (Format 3 — present in syzbot/newer kernels) |

The `state-flags` characters decode as: `.` = never seen in state, `+` = ever seen
in state, `-` = always seen in state, `?` = unknown. The four positions represent:
hardirq-safe, hardirq-unsafe, softirq-safe, softirq-unsafe. You do **not** need to
decode these in detail for crash analysis; record them as-is.

---

## Output table

Extract all locks into a **Locks Held** table:

| # | Lock name | Flags | Acquired in function | Offset | Source | In backtrace? |
|---|-----------|-------|---------------------|--------|--------|---------------|

From the example above:

| # | Lock name | Flags | Acquired in function | Offset | Source | In backtrace? |
|---|-----------|-------|---------------------|--------|--------|---------------|
| 0 | `sb_writers#5` | `{.+.+}-{0:0}` | `filename_unlinkat` | `0x1ad/0x730` | `fs/namei.c:5545` | Yes |
| 1 | `rcu_read_lock` | `{....}-{1:3}` | `rcu_lock_acquire.constprop.0` | `0x7/0x30` | `include/linux/rcupdate.h:300` | No |

To fill the "In backtrace?" column: check whether the **acquiring function**
(after stripping compiler suffixes such as `.cold`, `.part.N`, `.constprop.N`)
appears anywhere in the Backtrace table. Mark "Yes" or "No".

---

## Mandatory analysis rules

> ⚠️ These rules are **non-negotiable**. Violating them causes open-ended
> code exploration that grows exponentially and never terminates.

### Rule 1 — Only analyse acquisition sites that are in the backtrace

If the acquiring function **is in the backtrace**: the source code for that
function has already been (or will be) fetched as part of backtrace mapping.
You may reference that code when discussing how and why the lock was acquired —
no extra fetching is needed.

If the acquiring function **is NOT in the backtrace**: record the lock name and
flag it as "not in backtrace". **Stop there.** Do not:
- look up the function in the source tree
- read any file to find where the lock is taken
- follow any call chain to understand how the lock acquisition was reached

In the example above: `filename_unlinkat` IS in the backtrace → reference its
already-fetched source. `rcu_lock_acquire.constprop.0` is NOT → note that
`rcu_read_lock` was held, and move on.

### Rule 2 — Do not chase lock class hierarchies

Even when the acquiring function IS in the backtrace, do not try to find
every other place the same lock class is acquired or released elsewhere in
the kernel. Restrict the analysis to what is visible in the current crash.

### Rule 3 — Record but do not speculate about unknown lock types

If the lock name is unfamiliar (e.g. `sb_writers#5`, a per-superblock lock),
record it and note its type at a high level ("filesystem write lock"). Do not
read `super.h` or similar headers to reconstruct the full lock hierarchy.

---

## Lock activity table (Data Collection phase — after script has run)

After `backtrace_resolve.py` has completed and the function source code for
each backtrace entry is in hand, build a **Lock Activity** table. This table
captures which locks are **directly acquired or released** inside each
backtrace function — using only the source code already fetched by the
script, with no additional file reads.

### When to build it

Build this table only when a "locks held" block is present. It is part of
the Data Collection phase and must be completed before Phase 2 analysis.

### Source code constraint — absolutely no traversal

> ⚠️ **Scan only the source code already fetched by `backtrace_resolve.py`
> for each backtrace function. Do NOT open any other file, follow any
> call, or read any callee to determine what locks it takes. If a lock
> acquire/release is hidden inside a helper call, do not follow that
> helper — leave it unrecorded.**

The goal is a fast, bounded scan, not a complete lock graph.

### What to look for

Scan the function body for direct calls to standard kernel locking and
RCU primitives. Common patterns to recognise (non-exhaustive):

**Acquire** (lock taken): `spin_lock*`, `mutex_lock*`, `rwlock*` / `read_lock*` / `write_lock*`, `down*`, `rcu_read_lock*`, `srcu_read_lock*`, `rcu_lock_acquire`, `lock_acquire`, `preempt_disable*`, `local_irq_disable*`, `raw_spin_lock*`

**Release** (lock dropped): `spin_unlock*`, `mutex_unlock*`, `read_unlock*` / `write_unlock*`, `up*`, `rcu_read_unlock*`, `srcu_read_unlock*`, `rcu_lock_release`, `lock_release`, `preempt_enable*`, `local_irq_enable*`, `raw_spin_unlock*`

Record the call name and, where visible, the lock variable or argument
(e.g. `&inode->i_lock`, `rcu_read_lock` with no argument).

### Output table format

| Backtrace entry | Locks directly acquired | Locks directly released |
|---|---|---|
| `#N function_name` | lock calls with argument (if visible) | lock calls with argument (if visible) |

Leave a cell blank if no acquire/release calls are present in that function.
Use `—` if the function source was not resolved (skipped/note in script output).

### Example

For a backtrace containing `filename_unlinkat`, `iput`, and `shmem_evict_inode`,
the table might look like:

| Backtrace entry | Locks directly acquired | Locks directly released |
|---|---|---|
| `#0 shmem_undo_range` | — | — |
| `#1 shmem_evict_inode` | `mutex_lock(&inode->i_mutex)` | `mutex_unlock(&inode->i_mutex)` |
| `#2 iput.part.0` | — | — |
| `#3 filename_unlinkat` | `rcu_read_lock()` | `rcu_read_unlock()` |

---

## Using the lock activity table in analysis

> ⚠️ **The lock activity table is the sole source for lock analysis in
> Phase 2. Do NOT search the kernel source for other places locks are
> acquired or released, even if the table is incomplete.**

Use the table alongside the Locks Held table during the **What** and
**Where** steps:

- Cross-reference the Locks Held table against the Lock Activity table.
  If a held lock appears in the Lock Activity table as acquired but not
  released in any backtrace function, that confirms the lock is still held
  at crash time and the function that took it is visible in the trace.
- If a held lock does **not** appear in the Lock Activity table at all
  (acquisition function not in backtrace, and no direct acquire call found
  in any backtrace function), note it as "origin not visible in backtrace"
  and move on — do not search further.
- Use acquire/release imbalances within a single function (acquired but
  not released, or released without prior acquire) as evidence of the bug
  mechanism when relevant.

---

## Using the locks-held block in analysis (summary)

Once both the Locks Held table and the Lock Activity table are built,
consult them during the **What** and **Where** analysis steps:

- A held **sleeping-unsafe** lock (e.g. spinlock, RCU read-side) combined with
  a sleeping function call is itself the bug — the locks table confirms this
  directly without needing further code investigation.
- A held **mutex or semaphore** at the time of a UAF or memory corruption
  may indicate that the lock should have protected the freed object but
  failed to do so — note this in the report.
- Record both tables in the report under a "Locks Held" section, between
  the Backtrace table and the source code listings.
