# Basic Data Collection Flow

This file contains Phase 2 — the collection agent's procedure. Its sole
purpose is to gather all structured data from the oops with **no analysis**.

Crash-type-specific information steps are in [flows.md](flows.md):

| Crash Type | Extra information steps |
|------------|------------------------|
| Paging Request | [paging request steps](flows.md#unable-to-handle-paging-request-flow) |
| WARNING | [WARNING steps](flows.md#warning-flow) |
| BUG / BUG_ON | [BUG steps](flows.md#bug--bug_on-flow) |
| Panic | [Panic steps](flows.md#panic-flow) |

---

## Basic Data Collection flow

The purpose of this flow is to collect all structured data from the report,
with no analysis of the cause. It must be completed in full before any
analysis begins.

**Total budget: 25 minutes** for Phase 2. Note your start time on entry.
If any individual step (e.g. vmlinux download, source fetch) is not making
progress after 3 minutes, mark that item `*(unavailable — timed out)*` in
the report and move on. Stop Phase 2 at 25 minutes regardless, write
whatever is collected, and notify the user.

0.  ⛔ **FIRST THING — create the report file on disk right now, before reading
    any source or doing any analysis.** Create the output directory and write a
    skeleton `report.md` using the template in `templates/basic-report.md`.
    Fill in only what you already know from the oops text itself (crash type,
    process name, HEAD commit, MSGID). Leave all other sections as empty
    placeholders (`*(pending)*`). Save it immediately. This file will be
    updated at every checkpoint below. Do not proceed to step 1 until the file
    exists on disk.

1.  Read [fundamentals.md](fundamentals.md) and run the **General fundamentals extraction** primitive.
    ⛔ **Update the report now** — fill in the Key Elements and Kernel Modules sections. Save before continuing.
2.  Read [backtrace.md](backtrace.md) and run the **Backtrace extraction** primitive.
    ⛔ **Update the report now** — fill in the Backtrace table. Save before continuing.
3.  If a "N locks held" block is present in the report: read [lockdep.md](lockdep.md)
    and run the **Locks held extraction** primitive.
4.  Run the **Code byte line extraction** primitive.
5.  Run the **CPU Registers** primitive.
6.  Run the **Linux distribution specific tasks** primitive (and the
    **General source tree fallback** if no distro is matched or SOURCEDIR
    is still unset) to download debug packages and fetch kernel source.
    **If `prefetch.md` exists and marks VMLINUX and SOURCEDIR as `ready`,
    skip the vmlinux download and git checkout sub-steps — use the paths
    from prefetch.md directly.** Only skip a sub-step if prefetch.md
    explicitly marks it `ready`; fall back to the full step for any item
    marked `failed` or `not applicable`.
7.  Read [mapping.md](mapping.md) and run the **Mapping backtrace lines to code** primitive.
8.  If a "locks held" block is present: build the **Lock Activity** table
    as described in [lockdep.md](lockdep.md) — scan each backtrace function's
    already-fetched source for direct lock acquire/release calls only; no
    additional file reads or call traversal.
9.  ⛔ **HARD CHECKPOINT — update the report NOW before doing anything else.**
    Do not start Phase 3. Do not read more source files. Do not run more git commands.
    Update the report file (created in step 0) with all data now in hand:
     - Add a prominent banner at the top of the report body (just below the
       origin summary, before Key Elements):
       `> ⏳ **Analysis in progress** — Phase 2 data collection complete; Phase 3 analysis not yet run.`
     - Fill in any sections not yet written: Registers, Backtrace source code
       listings, Locks Held table, Lock Activity table (if present).
     - Leave the **What / How / Where**, **Security note**, and
       **Analysis reply email** sections absent (they do not exist yet).
     - After saving, notify the user: *"Phase 2 complete — initial report
       saved to [path]. Starting Phase 2 analysis now."*
     - Only after the report file is confirmed written on disk: proceed to Phase 3.
