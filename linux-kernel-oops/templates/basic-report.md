# Linux kernel crash report

<Summarize the origin of the data based on the prompt; if it comes from a
bug tracker, provide a URL to the report. If the source is an image or
screenshot, include the image here immediately after the summary line:

## Source screenshot

![Kernel oops screenshot](oops.png)

Omit this section entirely if the source is not an image.>

## Key elements

<Put the "Key Elements" table here>


## Kernel modules

<Put the "Modules List" table here using the format below.
If space is limited, prioritize rows with a "Y" in the "Backtrace" column.>

| Module | Flags | Backtrace | Location | Flag Implication |
| ------ | ----- | --------- | -------- | ---------------- |


## Backtrace

<Fill this table first, then write the "Backtrace source code" section below,
then come back here and update the "Source location" cells as follows:
for each row that has a matching subsection in "Backtrace source code",
replace the plain location text with a Markdown link to that subsection's
anchor, so the reader can click directly to the analysis.

Anchor derivation rules (GitHub/CommonMark): lowercase all text; replace
spaces with hyphens; remove all punctuation except hyphens and underscores
(backticks, colons, parentheses, dots, em-dashes are all removed);
underscores in identifiers are preserved.

Example — heading `### 1. \`bmc150_accel_set_interrupt\` — crash site (\`bmc150-accel-core.c:551\`)` becomes:
  `[bmc150-accel-core.c:551](#1-bmc150_accel_set_interrupt--crash-site-bmc150-accel-corec551)`>

| Address | Function | Offset | Size | Context | Module | Source location |
| ------- | -------- | ------ | ---- | ------- | ------ | --------------- |


## Locks held

<Include this section only if a "N locks held" block was present in the oops.
Omit entirely if no locks-held block was found.

Two tables, per lockdep.md:

1. **Locks Held table** — one row per lock entry in the "N locks held" block.

| # | Lock name | State flags | Nesting | Acquired at |
|---|-----------|-------------|---------|-------------|

2. **Lock Activity table** — built by scanning the backtrace source listings
for direct lock acquire/release calls. One row per acquire/release observed.

| Backtrace # | Function | Lock name | Action | Source location |
|-------------|----------|-----------|--------|-----------------|
>


## Backtrace source code

<Only include this section if SOURCEDIR is available. Make a subsection for each of the
first four high-confidence backtrace entries (those without a "?" prefix), formatted
using the "Reporting a source code function" primitive.

Two requirements from that primitive are critical and must not be skipped:
- Place a Markdown hyperlink to the online git tree immediately before every code block.
- Prefix every original source line with its actual file line number, right-aligned.
These are both mandatory.>


## What-how-where analysis

<Include this section only if the Deep Analysis flow was run; omit it otherwise.
If included, add three subsections — "What", "How", and "Where" — each containing
the corresponding part of the root-cause analysis.>


## Bug introduction

<Include this section only if the Bug introduction analysis step was run and
produced a result. Omit entirely if the step was skipped (Unknowable How) or
no candidate was found within the budget.

If a candidate commit (or series) was found, include:
- The commit hash(es) as Markdown links, author, date, and subject
- A brief explanation of why this commit is the likely introduction point
- If multiple candidates exist, list all but clearly mark the primary suspect
- If the blame version was a fallback tag (not exact), note that here
- If no candidate was found: "Bug introduction commit not identified within search budget">


## Security note

<Include this section only when the Security Assessment step produced a
reportable outcome (CVE confirmed, or high-confidence classification from
the structured analysis). Omit it entirely in all other cases — do not write
"no security impact" or "unknown".>


## Analysis, conclusions and recommendations

<Provide a summary of the analysis, with conclusions and any
recommendations or next steps>
