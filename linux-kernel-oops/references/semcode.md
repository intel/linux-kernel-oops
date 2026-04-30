# semcode — Kernel Code Navigation MCP

**Demand-load this file** when the semcode MCP server is available and you
need to navigate kernel source code during analysis.

Source: https://github.com/masoncl/semcode-devel

---

## What semcode is

semcode is a semantic code-navigation MCP server that indexes a kernel source
tree into a local database and exposes fast, structured queries — function
lookup, call graph traversal, regex and vector search over function bodies, and
lore.kernel.org email search. It is **much faster and more precise** than
grepping files manually, and avoids the risk of reading the wrong file or
version.

All semcode functions are **git-aware** and default to the current HEAD commit.
Pass `git_sha` or `branch` to query a specific version. All regex patterns are
**case-insensitive by default** — no `(?i)` flag needed.

## Detecting availability

semcode is available when:
1. `semcode-indexing_status` returns a Git SHA that matches (or is close to)
   the kernel version being analysed.
2. A test query (e.g. `semcode-find_function` for `do_syscall_64`) returns a
   result rather than "not found".

If semcode is not available or returns no results, fall back to `grep`/`ripgrep`
on the source tree as normal.

## Index freshness — when to re-index

The index is stored in `.semcode.db` inside the kernel source tree. It is
incremental for git history, and uncommitted modifications to tracked files are
overlaid automatically (no re-index needed for local edits).

**Check freshness** with `semcode-indexing_status` or `semcode-list_branches`:
- **up-to-date**: indexed SHA matches current HEAD — safe to use.
- **outdated**: new commits have been added since indexing — results may miss
  recent changes. Re-index if the gap is significant for the crash being
  analysed.
- **wrong tree / no results**: index was built from a different kernel tree
  (wrong `.semcode.db`). Re-index the correct tree.

**How to re-index** — run in the kernel source directory:

```bash
cd /path/to/linux
semcode-index -s .
```

This is incremental — only new commits are scanned. A full re-index takes
several minutes on a large tree; an incremental update is fast.

### Agent re-index policy

- **`oops-workdir/linux`** is the agent's private
  kernel tree. Re-index it autonomously whenever the index is stale or
  mismatched — no user permission needed. Run `semcode-index -s .` from that
  directory and wait for it to finish before querying.

- **Any other kernel tree** (user's own source, distro tree, etc.) — do **not**
  re-index autonomously. Tell the user which tree needs re-indexing and the
  command to run, then wait.

---

## Operations

### Find a function or macro — `find_function`

Look up a function or macro by name (or regex). Returns full body, file
location, parameters, return type, and caller/callee counts.

**When to use:** You know a function name and want its source and location
without reading a file manually.

Key parameters: `name` (function/macro name or regex), `git_sha`, `branch`.

---

### Find a type or typedef — `find_type`

Look up a struct, union, enum, or typedef.

Key parameters: `name` (type name or regex), `git_sha`, `branch`.

---

### Find all callers — `find_callers`

Get every function that calls a given function or macro.

**When to use:** Tracing how execution reached a crash site; finding all
places a lock is acquired or a structure is modified.

Key parameters: `name`, `git_sha`, `branch`.

---

### Find all callees — `find_calls`

Get every function called by a given function or macro.

**When to use:** Understanding what a function does; checking whether a lock
is released on all paths.

Key parameters: `name`, `git_sha`, `branch`.

---

### Trace a full call chain — `find_callchain`

Walk both callers (up) and callees (down) from a function to a configurable
depth.

**When to use:** Mapping the full path from syscall entry to a crash site, or
verifying that a call chain is plausible.

Key parameters: `name`, `up_levels` (default 2), `down_levels` (default 3),
`calls_limit` (default 15, 0 = unlimited), `git_sha`, `branch`.

Keep `up_levels` and `down_levels` small (2–3) to avoid overwhelming output.

---

### Search function bodies by regex — `grep_functions`

Find all functions whose body matches a regex, optionally filtered to a file
path pattern.

**When to use:** Finding every function in a subsystem that calls
`rcu_read_lock()`, acquires a specific lock, or references a struct field.

Key parameters: `pattern` (regex), `path_pattern` (optional path filter),
`verbose` (show full body, default false), `limit` (default 100),
`git_sha`, `branch`.

> Note: This scans indexed function bodies only — not comments, `#ifdef`
> blocks outside functions, or non-function-like macros.

---

### Vector / semantic function search — `vgrep_functions`

Semantic (embedding) search for functions matching a natural-language
description.

**When to use:** When a regex won't find what you need because you're looking
for a broad concept rather than a specific token (e.g. "memory allocation in
slab", "RCU grace period wait").

Key parameters: `query_text`, `path_pattern`, `limit` (default 10, max 100),
`git_sha`, `branch`.

> The database may not have embeddings indexed — check `indexing_status`.

---

### Extract symbols from a diff — `diff_functions`

Given a unified diff string, returns all functions and types touched.

**When to use:** Reviewing a patch for a proposed fix; checking which symbols
a known-good commit modified.

Key parameter: `diff_content` (diff text).

---

### Search git commits — `find_commit`

Search commits by subject, author, regex against message + diff, or symbols
changed. Supports single ref or range queries.

Key parameters: `git_ref`, `git_range` (mutually exclusive with `git_ref`),
`subject_patterns`, `author_patterns`, `regex_patterns` (AND'd),
`symbol_patterns`, `path_patterns`, `reachable_sha`, `verbose`, `page`.

> ✅ To find a backported commit: use `reachable_sha=HEAD` with
> `subject_patterns` — do NOT combine `reachable_sha` with `git_range`.

---

### Semantic commit search — `vcommit_similar_commits`

Vector search for commits similar to a text description.

Key parameters: `query_text`, `git_range`, `author_patterns`,
`subject_patterns`, `regex_patterns`, `symbol_patterns`, `path_patterns`,
`reachable_sha`, `limit` (default 10, max 50), `page`.

---

### Search lore.kernel.org email archives — `lore_search`

Search the kernel mailing list archive by sender, subject, body, symbols, or
recipients.

Key parameters: `from_patterns`, `subject_patterns`, `body_patterns`,
`symbols_patterns`, `recipients_patterns`, `message_id`, `verbose`,
`show_thread`, `show_replies`, `limit` (default 100), `since_date`,
`until_date`, `mbox`, `page`.

---

### Find lore emails for a commit — `dig`

Find mailing list threads related to a specific commit (by SHA, branch, HEAD,
etc.).

Key parameters: `commit`, `verbose`, `show_all`, `show_thread`,
`show_replies`, `since_date`, `until_date`, `page`.

---

### Semantic lore email search — `vlore_similar_emails`

Vector search over lore.kernel.org emails for a text description.

Key parameters: `query_text`, `from_patterns`, `subject_patterns`,
`body_patterns`, `symbols_patterns`, `recipients_patterns`, `limit`
(default 20, max 100), `since_date`, `until_date`, `page`.

> The database may not have lore embeddings indexed.

---

### Branch and index management

- `list_branches` — list indexed branches and their freshness
- `compare_branches(branch1, branch2)` — show merge base and ahead/behind
- `indexing_status` — check indexing progress, errors, timing

---

## Scope rules — mandatory

> ⚠️ semcode makes deep traversal *easy*, which makes it tempting to chase
> every caller and callee indefinitely. Apply the same scope limits as manual
> analysis:

1. **Lock analysis**: follow the rules in `lockdep.md` — use semcode to find
   lock acquire/release calls within backtrace functions; do not recursively
   chase callers outside the backtrace.
2. **How step**: limit call chain depth to what is needed to answer one
   specific "How did X happen?" question. Stop when you have a plausible
   answer; do not exhaustively map the entire subsystem.
3. **Where step**: use semcode to verify a proposed fix location or find
   analogous patterns — do not use it to produce an encyclopaedic survey of
   every related function.

---

## Practical workflow for lock origin searches

When the lockdep Locks Held table shows a lock whose acquisition function is
**not** in the backtrace, use semcode to narrow the search efficiently:

1. **Identify plausible backtrace callers** of the acquisition function
   (e.g. the lock was held when `vfs_unlink` ran — look inside its call tree).

2. **Get callees** of the relevant backtrace function:
   `semcode-find_calls(name="vfs_unlink")`

3. **Grep for the lock primitive** in those callees:
   `semcode-grep_functions(pattern="rcu_read_lock", path_pattern="fs/dcache")`

4. **Look up matching functions** to check whether the unlock is balanced:
   `semcode-find_function(name="dput")`

5. **Stop when you have a plausible candidate or have exhausted direct
   callees** — do not recurse further than one level beyond the backtrace.

---

## Example: tracing `rcu_read_lock` through `vfs_unlink`

From the syzbot BUG `69eab803` (shmem sleeping in RCU critical section):

```
find_callchain(name="vfs_unlink", up_levels=0, down_levels=2)
→ callees include: d_delete_notify, fsnotify_unlink, inode_lock/unlock, ...

grep_functions(pattern="rcu_read_lock", path_pattern="fs/dcache")
→ hit: dput() acquires rcu_read_lock()

find_function(name="dput")
→ rcu_read_lock(); fast_dput() or finish_dput() — both release it ✓

find_function(name="finish_dput")
→ __releases(RCU) annotation — balanced on all paths ✓
```

Result: `dput()` is balanced; the RCU lock origin is not in the direct
`vfs_unlink` call path — likely in an LSM hook or filesystem-specific
callback not visible from the backtrace.
