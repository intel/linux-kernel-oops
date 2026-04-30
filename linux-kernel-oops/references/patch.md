# Preparing a patch email

**Only invoke this when the analysis produced a new fix patch
(i.e., `report.patch` was written to the archive). Do NOT invoke it when
the resolution is an existing upstream commit found via git search.**

Use the template at
`linux-kernel-oops/templates/patch-email-template.md` as the
structure. Fill every field as described below, then save the result.

All content must be strict ASCII. Names of people are the only exception
(UTF-8 is acceptable there).

## Writing style

Apply these rules consistently across the subject line, bug description,
fix rationale, and fix description:

- **Imperative mood.** Write as if giving a command: "Fix zero-size
  range init", "Guard against absent hardware", "Skip registration when
  size is zero." Avoid past tense ("Fixed", "Added") and present
  progressive ("Fixing").
- **Expand acronyms on first use.** When introducing a subsystem name,
  hardware block, or technical abbreviation that is not universally
  known (outside the immediate driver), spell it out once followed by
  the acronym in parentheses, then use the short form after that.
  Example: "Global Data Share (GDS)" on first mention, then "GDS"
  thereafter. Skip expansion only for truly universal terms (e.g. CPU,
  GPU, DMA, IRQ, NULL).
- **No filler.** Omit phrases like "This patch", "This commit",
  "Note that", "It should be noted". Start sentences with the subject.
  Exception: the mandatory attribution opening sentence ("This patch is
  based on a BUG as reported …") is required and not considered filler.
- **Precision over brevity.** A slightly longer sentence that is
  unambiguous is better than a terse one that requires guessing.

## Step 1 — Read sender identity

Read `~/.gitconfig` and locate the `[user]` section. Extract:
- `name` → used for `From:` and `Signed-off-by:`
- `email` → used for `From:` and `Signed-off-by:`

This is **mandatory**. Do not invent or guess these values.

## Step 2 — Determine the subsystem tag

Run `git log` on each file changed by the patch to find the prevailing
subject-line prefix used by recent commits:

```bash
git -C oops-workdir/linux log --oneline -20 -- <patched-file>
```

Scan the subjects for a repeating pattern such as `drm/amdgpu:`,
`net: l3mdev:`, or `mm/huge_memory:`. Use that exact pattern — do not
invent your own. If multiple files are patched, use the prefix of the
most-touched subsystem.

## Step 3 — Write the Subject line

```
Subject: [PATCH] <subsystem>: <short imperative description>
```

The description should be a short imperative phrase (e.g.
"fix zero-size GDS range init on RDNA4"). Keep the full subject line
under 75 characters.

## Step 4 — Write the bug description

Open with a mandatory attribution sentence:

```
This patch is based on a <crash-type> as reported by <Name> at <URL>.
```

- **`<crash-type>`**: match the CRASH_TYPE from the Key Elements table —
  `BUG`, `Oops`, `WARNING`, or `Panic`. Use the exact kernel term.
- **`by <Name>`**: include only if the reporter's name is known (e.g.
  from an lkml email or a bug tracker's reporter field). Omit the
  "by <Name>" clause entirely if the name is not available.
- **`<URL>`**: the most direct URL to the original report — prefer a
  lore.kernel.org link if one exists, otherwise use the bug tracker URL.

Then continue with 2–3 paragraphs (up to 5 for very complex bugs)
describing how the bug occurs. Walk through the code in execution order:
what triggers it, what invariant is violated, and what the crash symptom
is. Wrap every line at 72 characters.

**If `CONFIG_REQUIRED` is set in the Key Elements table:** add a sentence
at the end of the bug description noting that the crash only occurs when
that option is enabled. Example:

```
This crash only occurs when CONFIG_DEBUG_VM is enabled.
```

Omit this sentence if `CONFIG_REQUIRED` is `(unconditional — fires in
all builds)`.

## Step 5 — Write the fix rationale (optional)

Include one paragraph only if multiple fixes were considered during the
What–How–Where analysis. Briefly explain why this fix was chosen over the
alternatives. Omit entirely if only one fix was considered.

## Step 6 — Write the fix description

1–2 paragraphs describing how the fix solves the problem. Favour
explaining the *mechanism* over literally transcribing what the code
does. Exception: for trivial fixes (e.g. "add a NULL check", "guard
against zero size"), a direct description is fine because no higher-level
explanation adds value. Wrap every line at 72 characters.

## Step 7 — Fill in the tags

Add tags in this order, omitting optional ones that do not apply:

| Tag | Rule |
|-----|------|
| `Reported-by: <name> <email>` | Include if the reporter's name and email are known (e.g. from the lkml `From:` header or a bug tracker's reporter field). Omit entirely if the reporter is anonymous or unknown. **syzbot special case**: syzbot emails always include an explicit request of the form *"If you fix the bug, please add the following tag to the commit message: `Reported-by: syzbot+<hash>@syzkaller.appspotmail.com`"* — copy this tag **verbatim** from the oops email. Do not reconstruct it; the hash encodes the bug report ID and must be exact. |
| `Link: https://lore.kernel.org/<msgid>` | Include if a MSGID is known. |
| `Link: <bug-tracker-URL>` | Include if the bug came from Launchpad, Bugzilla, etc. |
| `Oops-Analysis: <URL>` | Read the external URL base from `local.md` (look for the `External URL for reports` entry) and construct `<base>/<source>/<id>/report.html`. Always include this tag. |
| `Fixes: <hash> ("<subject>")` | Include if `INTRODUCED-BY` was identified. Use the full 12-char short hash and exact commit subject. |
| `Assisted-by: <agent>:<model> linux-kernel-oops.` | **Mandatory.** Replace with the actual agent name and model version. |
| `Signed-off-by: <name> <email>` | **Mandatory.** Same name and email as `From:`. |
| `Cc: <address>` | One line per address — see Step 8. |

**Never** include a `Co-authored-by:` line in a patch email. This is an AI-assisted analysis tool, not a co-author of the code.

## Step 8 — Generate the Cc list

Run `get_maintainer.pl` from the kernel source tree on the patch file:

```bash
perl oops-workdir/linux/scripts/get_maintainer.pl report.patch
```

`get_maintainer.pl` often returns many addresses. Trim the list to at
most **5 entries**, selecting in this priority order:

1. **Mailing lists** (addresses containing `@lists.` or `@vger.`) —
   always keep these; they give the patch the widest relevant audience.
   If there are more than 5 lists alone, keep all of them (the 5-cap
   applies to the combined list, not lists alone).
2. **Designated maintainers** (tagged `(maintainer)`) — fill remaining
   slots up to the cap.
3. **Reviewers / supporters** — only if slots remain after 1 and 2.

Omit the rest. If `get_maintainer.pl` is not available or fails, omit
the `Cc:` lines and note the omission.

## Step 9 — Assemble the full email

After the last `Cc:` line, add a `---` separator line, then the diffstat,
then the patch body:

```
---
<output of: git apply --stat report.patch>

<unified diff — the full content of report.patch>
```

## Step 10 — Validate the patch

Run:

```bash
git -C oops-workdir/linux apply --check ../reports/<path>/report.patch
```

If the check fails, correct the patch until it applies cleanly before
proceeding.

## Step 11 — Save the email

Write the complete email (From through end of patch) to
`patch-email.txt` in the same archive directory as `report.md`.
Do not display it inline — saving to the archive is sufficient.

## Step 12 — Generate git-send-email.sh

Create a shell script `git-send-email.sh` in the same archive directory.
`git send-email` reads `Cc:` addresses automatically from the patch
headers, so the script only needs `--to=`: the primary subsystem mailing
list — the first (most specific) list address from the `Cc:` lines
(addresses containing `@lists.` or `@vger.`).

```bash
#!/bin/sh
# Review before sending:
#   - Adjust --smtp-server / --smtp-user if not already configured
#     in ~/.gitconfig
#   - --annotate opens the patch in $EDITOR for a last review before send

git send-email \
    --annotate \
    --from="$(git config user.name) <$(git config user.email)>" \
    --to="<primary-subsystem-list>" \
    "$(dirname "$0")/patch-email.txt"
```

If a Message-ID is available from the analysis (e.g. the lore.kernel.org
MSGID of the bug report thread), add `--in-reply-to="<MSGID>"` to the
command. If no MSGID is known, omit `--in-reply-to` entirely — do not
leave a placeholder.

Make the script executable:

```bash
chmod +x git-send-email.sh
```
