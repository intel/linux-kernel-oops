# Fetching an OOPS from a Bug Tracker

Use this primitive when the user provides a bug tracker URL or ID rather than
raw OOPS text. It fetches the bug report, extracts any embedded OOPS, saves
it to the working directory, and hands off to the normal analysis flow.

Supported bug trackers:

| Tracker | URL pattern | Example |
|---------|-------------|---------|
| Launchpad | `https://bugs.launchpad.net/...+bug/<ID>` | `+bug/2148595` |
| Kernel Bugzilla | `https://bugzilla.kernel.org/show_bug.cgi?id=<ID>` | `?id=220772` |
| Debian BTS | `https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=<ID>` | `?bug=939277` |
| Red Hat Bugzilla | `https://bugzilla.redhat.com/show_bug.cgi?id=<ID>` | `?id=1718414` |

A bare integer (e.g. `2148595`) is ambiguous — apply these rules before
asking the user:

- **"Ubuntu bug N"** or **"LP: #N"** → Launchpad
- **"Fedora bug N"** or **"RHBZ #N"** or **"Red Hat bug N"** → Red Hat Bugzilla
- **"Debian bug N"** or **"BTS #N"** → Debian BTS
- **"kernel bug N"** or **"kernel.org bug N"** → Kernel Bugzilla

If none of these contextual cues are present, ask the user which tracker the
ID refers to before proceeding.

## Step 1 — Fetch the bug page

```bash
# Launchpad
curl -sL "https://bugs.launchpad.net/ubuntu/+source/linux/+bug/<ID>" \
  -o oops-workdir/bug-lp-<ID>.html

# Kernel Bugzilla
curl -sL "https://bugzilla.kernel.org/show_bug.cgi?id=<ID>" \
  -o oops-workdir/bug-bz-<ID>.html

# Debian BTS
curl -sL "https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=<ID>" \
  -o oops-workdir/bug-deb-<ID>.html

# Red Hat Bugzilla
curl -sL "https://bugzilla.redhat.com/show_bug.cgi?id=<ID>" \
  -o oops-workdir/bug-rh-<ID>.html
```

Use `oops-workdir/` as the download directory and name the file
`bug-lp-<ID>.html` (Launchpad), `bug-bz-<ID>.html` (Kernel Bugzilla),
`bug-deb-<ID>.html` (Debian BTS), or `bug-rh-<ID>.html` (Red Hat Bugzilla).

## Step 2 — Extract the OOPS text

Scan the downloaded HTML for lines that are characteristic of a kernel OOPS:
`BUG:`, `Oops:`, `WARNING:`, `Kernel panic`, `Call Trace:`, `RIP:`, `[ cut here ]`.

**Launchpad:** OOPS text typically appears as plain text inside `<pre>` or
`<div class="comment-text">` elements, or as a linked attachment. Check for
attachment links (`.txt` files) in the page — if found, download and inspect
those too:
```bash
grep -o 'href="[^"]*\.txt[^"]*"' oops-workdir/bug-lp-<ID>.html | head -10
```

**Kernel Bugzilla / Red Hat Bugzilla:** Both use the same Bugzilla software.
OOPS text usually appears in the bug description or a comment inside
`<pre class="bz_comment_text">` elements, or as an attachment.
Check for attachments similarly.

**Debian BTS:** OOPS text typically appears in the body of a mail message
rendered inside `<pre>` elements, or as a linked attachment (`.txt` or
`.gz`). The page may contain multiple mail messages (original report +
replies); scan all of them. Check for attachment links:
```bash
grep -o 'href="[^"]*bugreport[^"]*msg[^"]*"' oops-workdir/bug-deb-<ID>.html | head -10
```
If attachments are found, download and inspect them:
```bash
curl -sL "https://bugs.debian.org<attachment-path>" -o oops-workdir/bug-deb-<ID>-attach.txt
```

Extract the OOPS block — the contiguous section from the first `BUG:`/`Oops:`
line through the end of the `Call Trace:` / `---[ end trace ]` block — and
save it to `oops-workdir/<tracker>-<ID>-oops.txt`:
```bash
# Quick extraction using grep with context (adjust -A count as needed)
grep -A 60 "BUG:\|Oops:\|Kernel panic" oops-workdir/bug-lp-<ID>.html \
  | sed 's/<[^>]*>//g' > oops-workdir/lp-<ID>-oops.txt
```
Review the result and trim any HTML artefacts (tags, entities). If multiple
OOPS blocks are present in the same bug, extract all of them as separate files
(`-oops-1.txt`, `-oops-2.txt`, …) and ask the user which to analyse first.

## Step 3 — Confirm and proceed

Display the extracted OOPS text to the user for confirmation, then proceed
with the normal analysis flow starting from
[Classify the crash type](primitives.md#classify-the-crash-type).

Record the bug URL in the "Key Elements" table under a `BUG_URL` row so it
appears in the final report.
