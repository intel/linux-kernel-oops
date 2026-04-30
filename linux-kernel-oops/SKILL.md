---
name: linux-kernel-oops
description: "Expert x86 Linux kernel crash/oops analyser. Trigger whenever a kernel crash is involved in any form: (1) inline — keywords \"BUG:\", \"Oops:\", \"WARNING:\", \"Kernel panic\", \"Call Trace\", \"paging request\"; (2) in a file — \"I saved the crash/oops/dmesg in <file>\", \"oops.log\", etc.; (3) in dmesg — \"pull the crash from dmesg\", \"my system crashed, look at dmesg\"; (4) via bug tracker — \"Ubuntu/Fedora/Debian/kernel bug <N>\", or Launchpad, bugzilla.kernel.org, bugs.debian.org, bugzilla.redhat.com URLs containing a kernel crash. Do not analyse kernel crashes without consulting this skill's primitives and flows — it is the authoritative source for x86 kernel crash triage."
agent: true
model: sonnet
---

# Linux Kernel OOPS Analysis (x86)

This skill provides a structured approach to analyzing Linux kernel crash reports. It is divided into **Basic Primitives** for data extraction and **Analysis Flows** for diagnostic reasoning.

## Capabilities

| Category | Description | Reference |
|----------|-------------|-----------|
| **Primitives** | Low-level data extraction (registers, backtrace, taints) | [primitives.md](references/primitives.md) |
| **Analysis Flows** | Multi-agent pipeline orchestration (fetcher → collector → analyst → patcher/fact-checker) and crash-type-specific steps | [flows.md](references/flows.md) |
| **Agents** | Sub-agent definitions: fetcher (Step 1), collector (Step 2), analyst (Step 3), patcher (Step 4), fact-checker (Step 5), and patch reviewer (Step 6) | [agents/](agents/) |
| **Fundamentals** | Key Elements table, UNAME/distro, modules, taint, MSGID | [fundamentals.md](references/fundamentals.md) |
| **Backtrace** | Backtrace table construction, formats, IRQ/Task context | [backtrace.md](references/backtrace.md) |
| **Mapping** | Resolve backtrace offsets to source lines via gdb/addr2line | [mapping.md](references/mapping.md) |
| **Reporting** | Source code formatting rules, line numbers, summarization | [reporting.md](references/reporting.md) |
| **Distro: Debian** | Download, extract, and locate debug files for Debian | [debian.md](references/debian.md) |
| **Distro: Debian (pre-fetch)** | Fetcher-agent easy path: pool index lookup, `-dbg` package download | [fetch-debian.md](references/fetch-debian.md) |
| **Distro: Fedora** | Download, extract, and locate debug files for Fedora | [fedora.md](references/fedora.md) |
| **Distro: Fedora (pre-fetch)** | Fetcher-agent easy path: Koji RPM download, CKI git checkout | [fetch-fedora.md](references/fetch-fedora.md) |
| **Distro: Ubuntu** | Download, extract, and locate debug files for Ubuntu | [ubuntu.md](references/ubuntu.md) |
| **Distro: Ubuntu (pre-fetch)** | Fetcher-agent easy path: Launchpad git checkout, ddeb download | [fetch-ubuntu.md](references/fetch-ubuntu.md) |
| **Bug tracker fetch** | Fetch an OOPS from Launchpad, kernel Bugzilla, Debian BTS, or Red Hat Bugzilla | [bugtracker.md](references/bugtracker.md) |
| **Image transcription** | OCR a screenshot or decode a drm_panic QR code to extract OOPS text | [image.md](references/image.md) |
| **Patch email** | Prepare an LKML-ready patch email with send script when a new fix is created | [patch.md](references/patch.md) |
| **Analysis reply email** | Generate a plain-text LKML reply (`analysis-email.txt`) and send script when a MSGID is available and analysis confidence is high | [decode-email.md](references/decode-email.md) |
| **Locks held** | Parse the "N locks held" lockdep block; enforce strict scope limits to prevent unbounded code exploration | [lockdep.md](references/lockdep.md) |
| **Security assessment** | CVE lookup and structured severity classification (Paging Request, BUG, Panic only) | [security.md](references/security.md) |
| **semcode MCP** | Fast kernel code search, call graph traversal, lore email search via semcode MCP server | [semcode.md](references/semcode.md) |
| **Examples** | Sample OOPS reports for reference and testing | [assets/examples/](assets/examples/) |

## Usage Guidelines

1. **Classification**: Start by identifying the crash type (e.g., Paging Request, BUG, WARNING).
2. **Extraction**: Use the Basic Primitives to pull structured data (Backtrace, Registers, Taint state).
3. **Flow Execution**: Follow the specific Analysis Flow for the identified crash type to reach a root cause hypothesis.

---

## Basic Primitives

Detailed instructions for data extraction can be found in `references/primitives.md`.

- **Classify the crash type**: Determine if it's an Oops, Panic, BUG, or WARNING.
- **General fundamentals extraction**: Pull kernel version, process, module list, taint flags, and hardware info.
- **Backtrace extraction**: Clean and format the call trace.
- **Code byte line extraction**: Interpret the `Code:` line around the instruction pointer.
- **CPU Registers**: Extract GPRs and special registers (CR2, etc.).
- **Linux distribution specific tasks**: Download and unpack distro kernel packages for offline analysis (Debian, Fedora, Ubuntu).
- **Locating the vmlinux file**: Heuristics to find the debug symbols.
- **Locating a kernel module**: Find the `.ko` file for a loaded module.
- **Mapping backtrace lines to code**: Using `addr2line` or `gdb`.
- **Reporting a source code function**: Format abbreviated or full source listings with crash/call-site markers.
- **Generating HTML output**: Convert a Markdown report to HTML using `pandoc`.
- **General fundamentals extraction**: Demand-load [fundamentals.md](references/fundamentals.md) — Key Elements table, UNAME/distro detection, git-describe versions, crashing process, module list, taint flags, hardware name, email MSGID.
- **Backtrace extraction**: Demand-load [backtrace.md](references/backtrace.md) — unified Backtrace table, RIP as first entry, Format 1/2, IRQ/Task context markers, module data, build ID hashes, "?" marker handling.
- **Mapping backtrace lines to code**: Demand-load [mapping.md](references/mapping.md) — vmlinux vs module ELF selection, addr2line/gdb resolution, return-address correction, inlined function row splitting.
- **Reporting a source code function**: Demand-load [reporting.md](references/reporting.md) — mandatory online URL, line-number prefixes, ~NNN approximation, inlined functions/macros, struct inclusion, ≤20/>20 line summarization.
- **Transcribing an OOPS from a screenshot or image**: Demand-load [image.md](references/image.md) — OCR via `marker_single` (marker-pdf package) with vision model fallback; QR-code path for drm_panic screens; records `IMAGE_SHA256` and `IMAGE_FILE` in Key Elements.
- **Structured archive**: Save reports to a source-keyed `reports/` directory (e.g. `reports/launchpad/<id>/`) with Markdown, HTML, and optional patch files. Prompts before overwriting existing reports.
- **Security assessment**: Demand-load [security.md](references/security.md) — CVE lookup via lore.kernel.org, and structured 4-step severity classification. Run after Deep Analysis for Paging Request, BUG/BUG_ON, and Panic crashes. Only adds a Security Note when confidence is high.
- **Analysis reply email**: Demand-load [decode-email.md](references/decode-email.md) — plain-text LKML reply to the original report thread, with optional fix mention, decoded backtrace, and analysis. Only generated when a MSGID is available and analysis confidence is high.
- **Locks held**: Demand-load [lockdep.md](references/lockdep.md) — parse the "N locks held" lockdep block into a table; enforce mandatory scope rules to prevent unbounded code exploration.
- **semcode MCP navigation**: Demand-load [semcode.md](references/semcode.md) — when the semcode MCP server is available, use it for fast function lookup, call graph traversal, regex/vector search over function bodies, commit history search, and lore.kernel.org email search. Check index freshness before querying; re-index `oops-workdir/linux` autonomously if stale.

## Analysis Flows

Detailed diagnostic steps can be found in `references/flows.md`.

- **Entry point**: Initial triage and classification.
- **"Unable to handle paging request"**: Memory access violation analysis.
- **WARNING**: Non-fatal but significant kernel issues.
- **BUG / BUG_ON**: Intentional kernel assertions.
- **Panic**: Fatal system state analysis.
