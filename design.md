# Design: linux-kernel-oops

This document is for contributors who want to understand how the skill is
designed and how the pieces fit together. For installation and usage, see
[README.md](README.md).

---

## Filesystem layout

```
linux-kernel-oops/          Root of the skill
├── SKILL.md                    Entry point; capabilities table loaded by the agent
├── agents/                     One agent definition file per pipeline step
├── references/                 Reference documents demand-loaded by agents
├── scripts/                    Helper Python scripts (backtrace resolver, QR decoder)
├── templates/                  Output file skeletons (report, patch email, analysis email)
├── assets/                     Real-world oops files used for testing and evals
└── evals/                      Structured eval test cases (evals.json)
```

### [`agents/`](linux-kernel-oops/agents/)

Each file defines one agent: its identity, model preference, inputs/outputs,
and a link to the reference file that carries the detailed procedure.

| File | Step | Role |
|------|------|------|
| [`fetcher.agent.md`](linux-kernel-oops/agents/fetcher.agent.md) | 1 | Pre-fetch vmlinux, kernel source tree, distro packages |
| [`collector.agent.md`](linux-kernel-oops/agents/collector.agent.md) | 2 | Extract all structured data from the oops |
| [`analyst.agent.md`](linux-kernel-oops/agents/analyst.agent.md) | 3 | Root cause analysis; propose a fix |
| [`patcher.agent.md`](linux-kernel-oops/agents/patcher.agent.md) | 4 | Format an LKML-ready patch email |
| [`factchecker.agent.md`](linux-kernel-oops/agents/factchecker.agent.md) | 5 | Verify source quotes, line numbers, and indentation |
| [`patchreviewer.agent.md`](linux-kernel-oops/agents/patchreviewer.agent.md) | 6 | Gate the patch on a correctness checklist |

### [`references/`](linux-kernel-oops/references/)

Procedure documents loaded on demand. Never loaded wholesale — agents pull in
only what they need for the current task.

| File | Purpose |
|------|---------|
| [`flows.md`](linux-kernel-oops/references/flows.md) | Orchestration entry point; pipeline step descriptions and todo tracking |
| [`collection-flow.md`](linux-kernel-oops/references/collection-flow.md) | Step 2 data collection protocol |
| [`analysis-flow.md`](linux-kernel-oops/references/analysis-flow.md) | Step 3 What/How/Where analysis protocol |
| [`primitives.md`](linux-kernel-oops/references/primitives.md) | Low-level extraction primitives (backtrace, registers, vmlinux, …) |
| [`fundamentals.md`](linux-kernel-oops/references/fundamentals.md) | Key Elements table, UNAME/distro detection, taint flags |
| [`backtrace.md`](linux-kernel-oops/references/backtrace.md) | Backtrace table construction, format variants, IRQ/Task context |
| [`mapping.md`](linux-kernel-oops/references/mapping.md) | Resolve backtrace offsets to source lines via gdb/addr2line |
| [`reporting.md`](linux-kernel-oops/references/reporting.md) | Source code formatting rules, URL patterns, crash-site markers |
| [`patch.md`](linux-kernel-oops/references/patch.md) | LKML patch email format (subject, tags, Cc, send script) |
| [`decode-email.md`](linux-kernel-oops/references/decode-email.md) | Analysis reply email format |
| [`security.md`](linux-kernel-oops/references/security.md) | CVE lookup and structured severity classification |
| [`lockdep.md`](linux-kernel-oops/references/lockdep.md) | Parse the "N locks held" lockdep block |
| [`semcode.md`](linux-kernel-oops/references/semcode.md) | semcode MCP server for fast kernel code and commit search |
| [`bugtracker.md`](linux-kernel-oops/references/bugtracker.md) | Fetch oops from Launchpad, Bugzilla, Debian BTS |
| [`image.md`](linux-kernel-oops/references/image.md) | OCR screenshot or decode drm_panic QR code |
| [`debian.md`](linux-kernel-oops/references/debian.md) | Debian debug package download, Salsa git tree |
| [`ubuntu.md`](linux-kernel-oops/references/ubuntu.md) | Ubuntu ddeb download, Launchpad git tree |
| [`fedora.md`](linux-kernel-oops/references/fedora.md) | Fedora debuginfo RPM, CKI kernel-ark git tree |
| [`fetch-debian.md`](linux-kernel-oops/references/fetch-debian.md) | Fetcher pre-fetch procedure for Debian |
| [`fetch-ubuntu.md`](linux-kernel-oops/references/fetch-ubuntu.md) | Fetcher pre-fetch procedure for Ubuntu |
| [`fetch-fedora.md`](linux-kernel-oops/references/fetch-fedora.md) | Fetcher pre-fetch procedure for Fedora |

### [`scripts/`](linux-kernel-oops/scripts/)

| File | Purpose |
|------|---------|
| [`backtrace_resolve.py`](linux-kernel-oops/scripts/backtrace_resolve.py) | Resolve backtrace offsets to source lines; outputs `backtrace.json` |
| [`parse_oops.py`](linux-kernel-oops/scripts/parse_oops.py) | Structured extraction of key fields from raw oops text |
| [`decode_panic_qr.py`](linux-kernel-oops/scripts/decode_panic_qr.py) | Decode a drm_panic QR code from an image file |

### [`templates/`](linux-kernel-oops/templates/)

| File | Purpose |
|------|---------|
| [`basic-report.md`](linux-kernel-oops/templates/basic-report.md) | Output report skeleton |
| [`patch-email-template.md`](linux-kernel-oops/templates/patch-email-template.md) | Patch email skeleton |
| [`decode-email-template.md`](linux-kernel-oops/templates/decode-email-template.md) | Analysis reply email skeleton |

---

## The six-step pipeline

The skill uses a sequential pipeline of six specialized agents. Each agent has
a narrow scope; strict separation between steps prevents premature analysis
during data collection, which is the most common failure mode for single-agent
oops analysis.

Steps 4 and 5 run in parallel; Step 6 waits for Step 4.

```
Step 1: Fetcher      ──►  prefetch.md
Step 2: Collector    ──►  report.md   backtrace.json   collected.md
Step 3: Analyst      ──►  report.md (analysis)   report.patch   analysis-email.txt
Step 4: Patcher   ─┐ ──►  patch-email.txt   git-send-email.sh
Step 5: Fact-check ─┤ ──►  factcheck.md   report.md (fixes)
Step 6: Reviewer  ─┘ ──►  report.md (verdict)   [deletes send script on BLOCK]
```

The orchestrator follows [`references/flows.md`](linux-kernel-oops/references/flows.md)
to launch and sequence agents, track a todo list, and regenerate `report.html`
after all steps complete.

---

## Step 1 — Fetcher

**Goal:** prepare everything the later steps will need before they start, so
they don't waste their time budget on network I/O.

**Agent:** [`agents/fetcher.agent.md`](linux-kernel-oops/agents/fetcher.agent.md)  
**Model:** small/fast  
**Procedure:** agent file is self-contained; per-distro pre-fetch procedures
are in [`fetch-ubuntu.md`](linux-kernel-oops/references/fetch-ubuntu.md),
[`fetch-debian.md`](linux-kernel-oops/references/fetch-debian.md),
[`fetch-fedora.md`](linux-kernel-oops/references/fetch-fedora.md)

The fetcher handles:
- Downloading and decompressing the syzbot `vmlinux` (can be 1–2 GB)
- Checking out the kernel source tree to the exact HEAD commit (`PATCH_BASE`)
- Distro-specific pre-fetch (download `.ddeb` / `.deb` / RPM to cache)
- Refreshing the semcode index for fast code search
- Cloning the review-prompts repository used by the patch reviewer

Output is a `prefetch.md` file in the report directory summarising what was
prepared and which paths were set (vmlinux location, SOURCEDIR, PATCH_BASE).

---

## Step 2 — Collector

**Goal:** extract all structured data from the oops. No analysis.

**Agent:** [`agents/collector.agent.md`](linux-kernel-oops/agents/collector.agent.md)  
**Model:** standard  
**Procedure:** [`references/collection-flow.md`](linux-kernel-oops/references/collection-flow.md)

The collector reads `prefetch.md` then works through a fixed extraction
checklist from [`references/primitives.md`](linux-kernel-oops/references/primitives.md):
classifying the crash type, building the Key Elements table, extracting the
backtrace, resolving offsets to source lines via
[`backtrace_resolve.py`](linux-kernel-oops/scripts/backtrace_resolve.py),
and reporting source code listings for the top backtrace frames.

Key rules:
- **Data only** — the collector does not draw conclusions or propose fixes
- Any step that exceeds the time budget is marked incomplete and skipped;
  the collector writes what it has and stops regardless
- `report.md` is the handoff document to the analyst; `backtrace.json` is
  the machine-readable companion

---

## Step 3 — Analyst

**Goal:** determine root cause and, where confidence is high, propose a fix.

**Agent:** [`agents/analyst.agent.md`](linux-kernel-oops/agents/analyst.agent.md)  
**Model:** standard  
**Procedure:** [`references/analysis-flow.md`](linux-kernel-oops/references/analysis-flow.md)

The analyst reads the collector's `report.md` and follows the
**What / How / Where** protocol:

- **What** — identify the exact failing condition
- **How** — trace how that condition arose; repeat recursively until the root
  cause is reached; apply the blame-layer heuristic (driver bugs more likely
  than subsystem bugs, which are more likely than core bugs)
- **Where** — identify the correct fix location and write a unified diff

If a fix is found, the analyst writes `report.patch` and runs a self-review
checklist (resource leaks, lock balance, error paths). If the self-review
finds issues, `report.patch` is suppressed and downstream patch agents do not
run.

The analyst also produces `analysis-email.txt` — a plain-text reply to the
original lore.kernel.org thread.

---

## Step 4 — Patcher

**Goal:** turn `report.patch` into a properly formatted LKML patch email.

**Agent:** [`agents/patcher.agent.md`](linux-kernel-oops/agents/patcher.agent.md)  
**Model:** standard  
**Conditional:** only runs if `report.patch` exists  
**Procedure:** [`references/patch.md`](linux-kernel-oops/references/patch.md)

The patcher applies the patch with `git apply`, formats the commit message,
fills in all required tags (`Reported-by`, `Fixes:`, `Link:`,
`Oops-Analysis:`, `Signed-off-by:`), determines the Cc list via
`get_maintainer.pl`, and produces:
- `patch-email.txt` — the mbox-format patch email
- `git-send-email.sh` — a ready-to-run send script

---

## Step 5 — Fact-checker

**Goal:** verify that all source code quotes and metadata in `report.md` are
accurate.

**Agent:** [`agents/factchecker.agent.md`](linux-kernel-oops/agents/factchecker.agent.md)  
**Model:** small/fast — the task is mechanical  
**Runs in parallel with:** Step 4

The fact-checker reads each fenced code block in `report.md`, extracts the
line numbers from the prefixes, and compares the content verbatim against the
git tree at `PATCH_BASE`. Discrepancies are silently fixed (wrong indentation,
line numbers off by a small amount) or flagged as warnings (structural
mismatches). The git tree is the sole authoritative source.

Output is `factcheck.md` (a structured audit log) and an updated `report.md`
with fixes applied.

---

## Step 6 — Patch reviewer

**Goal:** binary PASS/BLOCK gate on the patch before it could be sent to LKML.

**Agent:** [`agents/patchreviewer.agent.md`](linux-kernel-oops/agents/patchreviewer.agent.md)  
**Model:** small/fast  
**Conditional:** only runs if Step 4 produced `patch-email.txt`  
**Runs after:** Step 4

The reviewer loads the kernel technical-patterns review guide and checks the
patch against a six-item checklist: resource leaks, lock balance,
NULL/uninitialised dereference, error path coverage, caller contract changes,
and overall obviousness.

**PASS:** appends a `## Patch Review` section to `report.md`.  
**BLOCK:** also prepends `X-Patch-Review: BLOCKED` to `patch-email.txt` and
**deletes `git-send-email.sh`** to prevent accidental sending.

---

## Contributing

A few guidelines:

- **Keep `fetch-<distro>.md` and `<distro>.md` in sync.** If you update the
  full distro workflow, check the pre-fetch procedure too. Update both in the
  same commit.
- **Agent files describe identity and scope; reference files describe
  procedure.** Put detailed step-by-step instructions in a reference file and
  link to it from the agent file.
- **Primitives vs flows.** A *primitive* (in [`primitives.md`](linux-kernel-oops/references/primitives.md))
  is a self-contained extraction task — it takes raw input and produces
  structured data with no conclusions. A *flow* (in
  [`flows.md`](linux-kernel-oops/references/flows.md) or a dedicated
  `*-flow.md`) orchestrates primitives and/or other flows toward a
  higher-level goal and may draw conclusions or produce output files. Flows
  can be used standalone or embedded inside an agent's procedure. Keep the
  distinction clean: if a new task produces data, add it as a primitive; if
  it drives reasoning or orchestration, add it as a flow.
- **The fact-checker is the safety net, not the primary path.** Fix root
  causes in agent instructions or scripts rather than patching up the
  fact-checker.
