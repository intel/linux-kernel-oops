```
From: User Name <user.email@example.com>
Subject: [PATCH] [subsystem]: Description

This patch is based on a <Oops|BUG|WARNING|Panic> as reported by
<Reporter Name> at <URL>.

<Description of how the bug happens, based on the Analysis. Prefer to
walk through the bug in sequence order of how the code executes.
Wrap all lines at 72 characters.>

<If identified multiple possible fixes, briefly (1 paragraph) discuss
why this solution was chosen over the other.
OPTIONAL — omit if only one fix was considered.>

<Describe the solution — 1 to 2 paragraphs.
Describe how the fix solves the problem, not what the code does.
Exception: trivial fixes like "add a NULL check" may be stated literally.
Wrap all lines at 72 characters.>

Link: https://lore.kernel.org/lore-msg-id
Link: <origin URL if not a msgid, such as a Ubuntu Launchpad bug URL>
Oops-Analysis: <URL to report — include only if context provides an external base URL for reports/>
Fixes: d245f9b4ab80 ("mm/zone_device: support large zone device private folios")
Assisted-by: AGENT_NAME:MODEL_VERSION linux-kernel-oops.
Signed-off-by: User Name <user.email@example.com>
Cc: <CC list from get_maintainer.pl, one address per Cc: line>

---
<diffstat — output of git diff --stat>

<the patch — unified diff>
```
