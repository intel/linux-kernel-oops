# Preparing an analysis reply email

**Only invoke this when ALL of the following are true:**

1. A **Message-ID** (MSGID) is available — from a lore URL, a saved raw
   email file, or the original request. Skip entirely if no MSGID is known.
2. The analysis was **high-confidence**: source code was found for the exact
   kernel version (or a very close match with no discrepancies identified
   during analysis).

This procedure generates `analysis-email.txt` — a plain-text reply to the
original report thread on LKML/lore — and `git-send-analysis.sh` to send it.

## Writing style

Apply the same rules as [patch.md](patch.md):
- Imperative mood; no filler phrases ("this patch", "note that").
- Expand acronyms on first use.
- Wrap all prose lines at 72 characters.
- Strict plain ASCII. Name/address fields may use UTF-8 for people's names.
- **Do NOT** mention "How-What-Where", "positive how", "negative how", or
  any skill-internal terminology in the email body.

---

## Step 1 — Normalise the Message-ID

You need two forms of the MSGID:

- **`msgid_bare`**: angle brackets stripped, URL-encoded.
  Example: `abc123@mail.gmail.com`
- **`msgid_header`**: angle-bracketed form for email headers.
  Example: `<abc123@mail.gmail.com>`

---

## Step 2 — Fetch original email headers

Use `web_fetch` with `raw: true` — `curl` returns HTTP 403 on lore `/raw` URLs:

```
web_fetch(url="https://lore.kernel.org/all/<msgid_bare>/raw", raw=true)
```

Parse the following headers. Note that RFC 2822 headers may be **folded**
across multiple lines (continuation lines start with whitespace) — unfold
them before extracting addresses:

- `From:` — original sender
- `Reply-To:` — if present, use instead of `From:` for the reply address
- `To:` — primary recipient(s)
- `Cc:` — CC list
- `Subject:` — original subject line

---

## Step 3 — Compute the recipient list

Collect all addresses (reply-all semantics):
- `Reply-To:` if present, otherwise `From:`
- All addresses from original `To:`
- All addresses from original `Cc:`

Deduplicate. Select exactly **one** as `PRIMARY_TO` using this priority:

1. A subsystem-specific mailing list in the combined set
   (e.g. `netdev@vger.kernel.org` — NOT `linux-kernel@vger.kernel.org`)
2. `linux-kernel@vger.kernel.org` (if no subsystem list is present)
3. The original `To:` address (if no mailing list is present at all)

All remaining addresses form the `CC_LIST`.

---

## Step 4 — Read sender identity

```bash
git config user.name
git config user.email
```

This is **mandatory**. Do not invent or guess these values.

---

## Step 5 — Write analysis-email.txt

Use `linux-kernel-oops/templates/decode-email-template.md` as the
structure. Fill every field as described below. Save the result to
`analysis-email.txt` in the archive directory alongside `report.md`.

**Headers** (top of file):

```
From: <name> <email>
Subject: Re: <original subject>
```

**Body sections** (strict ASCII, no markdown):

### Automation disclaimer

Keep the opening paragraph from the template exactly as written.

### Potential Existing Fix *(conditional)*

Include this section **only** if the **Where** step independently concluded
that a specific upstream fix exists. Write the 12-character short hash and
commit subject, followed by 1–2 paragraphs explaining why this commit
addresses the crash. Omit the section heading and all content if no fix
was identified.

### Decoded Backtrace

Include **all source code subsections from `report.md`'s
`## Backtrace source code` section** — not just the first few entries.
The agent already curated those subsections to cover the crash site,
call chain, and any analytically important functions; the email should
mirror that complete set.

Format each function as described in the "Reporting a source code
function" primitive, but in strict ASCII — no markdown.

**Mandatory formatting rule**: prefix every original source line with its
actual file line number, right-aligned to a consistent column width.
Do not wrap source code lines, even past 72 characters.

**Crash/call site marker (ASCII)**: use `->` as the prefix **before the
line number** (replacing the leading space), exactly as `→` is used in
report.md — but ASCII only since email must not contain UTF-8:

```
-> 3111  queue_work(hdev->workqueue, &hdev->cmd_work);
```

Additional inline insight uses `// <-` at the end of the line:

```
-> 3111  queue_work(hdev->workqueue, &hdev->cmd_work);  // hdev->workqueue is __WQ_DRAINING
```

**Omit the URL** to the online source tree (e.g. the gitlab.com or
github.com link). Those links are useful in the HTML report where the
reader can click them, but are distracting noise in a plain-text email.

### Tentative Analysis

If `patch-email.txt` already exists in the archive, reuse its analysis
text here verbatim (prevents divergence between the two emails). Otherwise,
write the What-How-Where analysis in execution order (what triggers it,
what invariant is violated, what the crash symptom is). Wrap all lines at
72 characters.

### Potential Solution *(conditional)*

Include only if a solution was identified (existing fix or new patch).
Stay within 1–2 paragraphs. Omit entirely if no solution was found.

### Security Note *(conditional)*

If `report.md` contains a `## Security note` section, include its content
here as a plain-ASCII paragraph under the heading `Security Note`. Strip
all markdown formatting (no `**bold**`, no backticks, no links — write
the CVE ID and URLs as plain text). Omit this section and its heading
entirely if `report.md` has no Security note section.

### More information

Include `Oops-Analysis:` with the **directory** URL (no `report.html`
suffix): read the base from `local.md` (`External URL for reports` entry)
and construct `<base>/<source>/<id>/`. Do **not** substitute the lore
MSGID URL — that is the original bug report, not the analysis.
Always include the `Assisted-by:` line.

---

## Step 6 — Generate git-send-analysis.sh

Create a shell script `git-send-analysis.sh` in the same archive directory.
One `--cc=` flag per address in `CC_LIST`.

```bash
#!/bin/sh
# Review before sending:
#   - Adjust --smtp-server / --smtp-user if not already configured
#     in ~/.gitconfig
#   - --annotate opens the email in $EDITOR for a final review before send

git send-email \
    --annotate \
    --from="$(git config user.name) <$(git config user.email)>" \
    --in-reply-to="<msgid_header>" \
    --to="<PRIMARY_TO>" \
    --cc="<addr1>" \
    --cc="<addr2>" \
    "$(dirname "$0")/analysis-email.txt"
```

Make the script executable:

```bash
chmod +x git-send-analysis.sh
```

Do not generate this script (or generate it with a comment explaining why
it is incomplete) if the original email headers could not be fetched.
