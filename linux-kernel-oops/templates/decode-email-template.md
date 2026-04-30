```
From: User Name <user.email@example.com>
Subject: Re: <original email subject>

This email is created by automation to help kernel developers
deal with a large volume of AI generated bug reports by decoding
oopses into more actionable information.

Potential Existing Fix

<If an existing commit was identified, Report the git hash and the subject 
of that commit here, followed by one or two paragraphs describing how this
fix would address this oops. If no fix was identified, leave out this as
well as the "Potential Existing Fix" line above>


Decoded Backtrace

<Include all source code sections from report.md's Source Code section,
in the same order. Format using the "Reporting a source code function"
primitive, but in strict ascii - not docbook. Omit the online URL link.
Do not wrap lines of source code, even if they exceed the 72 character
limit.

Mandatory formatting rule:
Prefix every original source line with its actual file line number, right-aligned.
>


Tentative Analysis

<Description of how the bug happens, based on the Analysis. Prefer to
walk through the bug in sequence order of how the code executes.
Wrap all lines at 72 characters.>


Potential Solution

<If a solution has been identified, describe briefly how this should be
done. Prefer to stay within two paragraphs, but for complex solutions, upto
four paragraphs is permitted>


Security Note

<If the security assessment produced a high-confidence outcome, include the
security note text here in plain ASCII (no markdown bold/italic). If no
high-confidence outcome was reached, omit this section and its heading.>


More information

Oops-Analysis: <URL to report — include only if context provides an external base URL for reports/>
Assisted-by: AGENT_NAME:MODEL_VERSION linux-kernel-oops.

```