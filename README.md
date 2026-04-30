# Linux Kernel OOPS Analysis — AI Agent Skill

An AI agent **skill** for expert analysis of Linux kernel OOPS crash reports
on x86. The skill gives an agent a structured, multi-step workflow for
extracting structured data from a crash report and reasoning toward a root
cause hypothesis.

## Examples

Real-world crash reports analysed end-to-end by the skill:

| Oops report | Analysis | Description |
|-------------|----------|-------------|
| [fedora-oops.txt](linux-kernel-oops/assets/fedora-oops.txt) | [example-1.md](docs/example-1.md) | Fedora 43, ZhiWei NA08H tablet — `bmc150_accel_core` NULL pointer dereference on interrupt-less hardware; upstream fix in v6.18 |
| [Launchpad #2134472](https://bugs.launchpad.net/ubuntu/+bug/2134472) | [example-2.md](docs/example-2.md) | Ubuntu 24.04 Noble, GCP — `l3mdev_fib_table_rcu` NULL dereference during VRF teardown; race with ARP neighbour timer in IRQ context |
| [lkml msgid aYN3JC_Kdgw5G2Ik@861G6M3](https://lore.kernel.org/lkml/aYN3JC_Kdgw5G2Ik@861G6M3/) | [example-3.md](docs/example-3.md) | Cloudflare Linux 6.18.7 — `VM_BUG_ON_FOLIO` in `filemap_fault`; THP folio split race placing sub-folios at wrong XArray indices; fix in v7.0-rc1, not yet in v6.18 stable |
| [bugzilla.kernel.org #221376](https://bugzilla.kernel.org/show_bug.cgi?id=221376) | [example-4.md](docs/example-4.md) | Custom 6.18.22 kernel, AMD RX 9070 XT (RDNA4/GFX12) — `DRM_MM_BUG_ON` in `drm_mm_init`; RDNA4 removed GDS/GWS/OA resources but `amdgpu_ttm_init` unconditionally passes zero-size ranges; no upstream fix found as of v6.19 |
| [lkml CAPHJ_VJeBAL_fk+…](https://lore.kernel.org/all/CAPHJ_VJeBAL_fk+P79guYTABZgW1hkcAz8t=c_nVK1mbn3_FYw@mail.gmail.com/) | [example-5.md](docs/example-5.md) · [patch email](docs/example-5-patch-email.txt) | Mainline 7.0.0-08391-g1d51b370a0f8, syzkaller ext4 image — `BUG_ON(pos+len > i_inline_size)` in `ext4_write_inline_data`; corrupted image bypasses inline-size guard; fix replaces `BUG_ON` with `ext4_error_inode()` |

---

## Example prompts

Once installed, you can talk to the agent naturally. A few examples:

**From a saved file**
> A customer reported a kernel oops — I saved the report in `crash.txt`.
> Please analyse it and provide recommendations.

**From the live system**
> My local system had a kernel crash. Can you pull the crash out of `dmesg`
> and provide a thorough analysis?

**From a Launchpad bug (Ubuntu)**
> Ubuntu bug 2148595 has a kernel crash. Can you fetch it and analyse the oops?

**From the kernel Bugzilla** ([see result](docs/example-4.md))
> Please analyse the oops in kernel.org bugzilla nr 221376.

**From the Debian bug tracker**
> Debian bug 939277 contains a kernel oops. Can you dig into the root cause?

**From Red Hat / Fedora Bugzilla**
> Fedora bug 1718414 on bugzilla.redhat.com shows a crash — what's wrong?

**From an lkml / lore.kernel.org email** ([see result](docs/example-3.md))
> An lkml post with msgid [`aYN3JC_Kdgw5G2Ik@861G6M3`](https://lore.kernel.org/lkml/aYN3JC_Kdgw5G2Ik@861G6M3/) has a kernel oops in it. Can you analyze this oops?

**From a syzkaller report on lore** ([see result](docs/example-5.md))
> Please analyze the oops in https://lore.kernel.org/all/CAPHJ_VJeBAL_fk+P79guYTABZgW1hkcAz8t=c_nVK1mbn3_FYw@mail.gmail.com/

---

## Contents

| Directory | Purpose |
|-----------|---------|
| `linux-kernel-oops/` | The installable skill |
| `linux-kernel-oops/references/` | Primitives and analysis flows (demand-loaded) |
| `linux-kernel-oops/assets/` | Example and real-world OOPS reports for testing |
| `linux-kernel-oops/evals/` | Evaluation test cases |

---

## Skill: `linux-kernel-oops`

**Expert analysis of Linux Kernel OOPS crash reports on x86.**

When a kernel crash report lands in your session — a `dmesg` snippet, a bug
report, a log file — this skill takes over. It provides:

- **Crash classification**: Oops, Panic, BUG/BUG_ON, or WARNING.
- **Structured data extraction**: kernel version, process context, CPU
  registers, taint flags, hardware info, and call trace in a clean table.
- **Backtrace mapping**: resolves each call-trace entry to a source file and
  line using `gdb` or `addr2line` against kernel debug symbols.
- **Distribution support**: automated download and unpacking of debug symbol
  packages for Debian, Fedora, and Ubuntu.
- **Deep analysis flows**: "What — How — Where" protocol for root cause
  identification; specialized flows for paging faults, WARNING, BUG, and panic.
- **Source reporting**: abbreviated or full source listings with crash-site
  markers, handling inlined functions and macro-expanded code correctly.

Trigger phrases: *"kernel oops"*, *"kernel crash"*, *"Call Trace"*,
*"BUG: unable to handle"*, *"WARNING: at"*, *"Kernel panic"*,
*"paging request"*, or any `dmesg` / crash log snippet.

---

## Installation

This skill follows the open [Agent Skills standard](https://agentskills.io).
The skill directory contains a `SKILL.md` file that any compatible agent can
load on demand. The same directory works across GitHub Copilot (CLI and
VS Code), Claude Code, OpenAI Codex, Gemini CLI, and other compatible agents.

| Agent | Project-level path | User-level path |
|---|---|---|
| GitHub Copilot CLI / VS Code | `.github/skills/` | `~/.copilot/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `.gemini/skills/` | — |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |

### GitHub CLI (`gh skill`) — recommended

The easiest way to install across any supported agent. Requires
[GitHub CLI v2.90.0](https://github.com/cli/cli/releases/tag/v2.90.0) or later.

```bash
# Install for all agents (user-level)
gh skill install intel/linux-kernel-oops linux-kernel-oops

# Install for a specific agent only
gh skill install intel/linux-kernel-oops linux-kernel-oops \
    --agent copilot --scope user

# Pin to a specific release tag for reproducibility
gh skill install intel/linux-kernel-oops linux-kernel-oops \
    --pin v1.0.0
```

Keep it up to date:

```bash
gh skill update linux-kernel-oops
```

### GitHub Copilot CLI

Skills are installed per-user under `~/.copilot/skills/`:

```bash
cp -r linux-kernel-oops ~/.copilot/skills/
```

### GitHub Copilot in VS Code

GitHub Copilot in VS Code loads skills from `.github/skills/` at project
level or `~/.copilot/skills/` at user level. Project-level skills can be
committed so the whole team benefits automatically:

```bash
# Project-level (commit to your repository)
mkdir -p .github/skills
cp -r linux-kernel-oops .github/skills/

# User-level (available in every project)
cp -r linux-kernel-oops ~/.copilot/skills/
```

VS Code also scans `.claude/skills/` and `.agents/skills/`, so a single
project-level installation covers GitHub Copilot, Claude Code, and Codex
simultaneously.

### Claude Code

Claude Code discovers skills in `.claude/skills/` (project) or
`~/.claude/skills/` (user):

```bash
# Project-level
mkdir -p .claude/skills
cp -r linux-kernel-oops .claude/skills/

# User-level
cp -r linux-kernel-oops ~/.claude/skills/
```

### OpenAI Codex

Codex reads skills from `.agents/skills/` at project level and from
`~/.agents/skills/` at user level:

```bash
# Project-level
mkdir -p .agents/skills
cp -r linux-kernel-oops .agents/skills/

# User-level
cp -r linux-kernel-oops ~/.agents/skills/
```

### Gemini CLI

Gemini CLI reads project skills from `.gemini/skills/`:

```bash
mkdir -p .gemini/skills
cp -r linux-kernel-oops .gemini/skills/
```

### OpenCode

OpenCode has native skill support and reads skills from `.opencode/skills/`:

```bash
mkdir -p .opencode/skills
cp -r linux-kernel-oops .opencode/skills/
```

For user-level installation, copy to `~/.config/opencode/skills/` instead.

---

## Local preparation

The skill works best when a Linux kernel git tree is available locally.
Create the working directory and clone the stable kernel tree into it once,
before using the skill for the first time:

```bash
mkdir -p oops-workdir
git clone https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/ \
    oops-workdir/linux
```

If you already have a local kernel git tree (e.g. at `~/src/linux`), you can
use it as a reference to avoid re-downloading all the objects — only the
missing delta is transferred:

```bash
mkdir -p oops-workdir
git clone --reference ~/src/linux \
    https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/ \
    oops-workdir/linux
```

> **Note:** the stable tree is several gigabytes without a reference. The
> clone is a one-time cost — the agent will keep the tree up to date with
> `git remote update` as needed.

The agent also adds distro-specific remotes (Fedora CKI, Ubuntu kernel,
etc.) to this same tree on demand, so a single clone serves all analyses.

## Optional: semcode MCP for faster kernel code navigation

The skill can use [semcode](https://github.com/masoncl/semcode-devel) — a
semantic code-navigation MCP server — to navigate the kernel source tree
significantly faster than manual file reads or grep. When semcode is
available, the agent uses it for function lookup, call graph traversal,
regex search over function bodies, and lore.kernel.org email archive search.

To use it, build and index semcode against `oops-workdir/linux`:

```bash
# build semcode (requires Rust and libclang)
git clone https://github.com/masoncl/semcode-devel
cd semcode-devel && cargo build --release

# index the kernel tree (one-time, ~several minutes)
cd /path/to/oops-workdir/linux
/path/to/semcode-devel/target/release/semcode-index -s .
```

Then add the MCP server to your agent configuration pointing at
`oops-workdir/linux` as the working directory. The index is incremental —
re-running `semcode-index -s .` after a `git pull` only scans new commits.

## License

See [COPYRIGHT.md](COPYRIGHT.md) for terms of use.
