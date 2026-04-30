# Reporting a Source Code Function

**Demand-load this file** when starting the Reporting a source code function step.

This primitive provides instructions for the reporting format
when asked to report out source code for a function that is part of the
backtrace. This assumes a SOURCEDIR entry is present in the "Key Elements"
table; if not available this task is not possible and the lack of
source code should be reported instead.

As a preparation step, get the full source code of the function as
present in the location provided by SOURCEDIR.

**Always** provide a URL to the online git location of the snippet as a
Markdown link immediately before the code block, so it is directly clickable.
This is mandatory — do not show source code without it.

**Only use `git.kernel.org` or the distro-specific git host listed below.
Do NOT use elixir.bootlin.com, lxr, or any other cross-reference site —
those are not the authoritative source trees.**

URL patterns by source:

**Mainline / syzbot / upstream** (`git tree: upstream` in syzbot email, or
plain mainline oops with no distro marker):
```
https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/<file>?h=<tag>#n<line>
```
Use the nearest `vX.Y-rcN` or `vX.Y` tag if known (e.g. from the HEAD
commit subject or UNAME). If only a commit hash is available, use `?id=<hash>`
instead of `?h=<tag>`.

**Stable tree** (UNAME of the form `X.Y.Z` with no distro suffix):
```
https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/<file>?h=v<X.Y.Z>#n<line>
```
Where `v<X.Y.Z>` is the exact version from UNAME.

**Fedora / CKI**: use the GitLab kernel-ark URL (see `fedora.md`):
```
https://gitlab.com/cki-project/kernel-ark/-/blob/<tag>/<file>?ref_type=tags#L<line>
```

**Ubuntu**: use the Launchpad kernel git tree (series from `ubuntu.md`):
```
https://git.launchpad.net/~ubuntu-kernel/ubuntu/+source/linux/+git/<series>/tree/<file>?h=Ubuntu-<version>#n<line>
```
Where `<series>` is e.g. `noble` and `Ubuntu-<version>` is the tag derived
from UNAME (see `ubuntu.md` for tag format details). If the exact tag is
unknown, use `h=Ubuntu-<version>` with the closest available tag.

**Debian**: use the Salsa kernel git tree:
```
https://salsa.debian.org/kernel-team/linux/-/blob/debian/<version>/<file>#L<line>
```
Where `debian/<version>` is the Debian package version derived from UNAME
(e.g. `debian/6.1.85-1`). If the exact tag is unknown, omit the URL and
note `(source from local tree only)`.

**Every line of source code must be prefixed with its actual file line number,**
right-aligned to the width of the largest line number in the block, followed
by a single space. This is mandatory — do NOT use inline
comments (e.g. `// line 526`) as a substitute. The output must look like:

```
  9 Code from Line 9
 10 Code from Line 10
521 static int bmc150_accel_set_interrupt(struct bmc150_accel_data *data, int i,
522                                       bool state)
523 {
524     struct device *dev = regmap_get_device(data->regmap);
525     struct bmc150_accel_interrupt *intr = &data->interrupts[i];
526     const struct bmc150_accel_interrupt_info *info = intr->info;
```

**Preserve all original indentation exactly.** Copy the source lines verbatim —
tabs and spaces must be reproduced as-is. Do not collapse, strip, or normalise
whitespace. A line that starts with a tab in the source must start with a tab
in the report (after the line-number prefix). Stripping indentation makes code
unreadable and loses structural information.

**When transcribing code from `backtrace_resolve.py` JSON output:** the
`function_source.code` field already contains the complete, properly-indented
source text. Copy it character-for-character into the fenced code block. Do
NOT re-type or reformat it — JSON string escapes (`\t`, `\n`) must be
interpreted as literal tab/newline characters, not collapsed or dropped.

**All file paths in the report must be relative**, not absolute. Use paths
relative to the project working directory (e.g. `oops-workdir/fedora/files/`),
never absolute paths (e.g. `/sdb1/arjan/git/oops-skill/oops-workdir/fedora/files/`).
This keeps reports portable and readable.

**If the exact line number is not known** (e.g. SOURCEDIR is unavailable and
you are relying on your built-in knowledge of the code), use `~NNN` as the prefix to
signal that the number is approximate. Do NOT omit the prefix entirely.
Example:
```
~521 static int bmc150_accel_set_interrupt(...)
~522 {
→~523     const struct bmc150_accel_interrupt_info *info = intr->info; // ← NULL here
```

**Marking the relevant line:** The line that is relevant in the backtrace
(as indicated by the provided offset/line number) must be marked with a `→`
prefix that replaces the 3-space indent before the line number, maintaining
column alignment with surrounding lines.

**Non-marker lines must always be prefixed with exactly 3 spaces** (`   `),
so that line numbers align with those on marker lines (`→  ` and `-> ` each
occupy 3 characters). Never emit a line number flush with column 1 unless it
is itself a marker line. Example:

```
   638		if (kobj) {
→  643			kref_get(&kobj->kref);
   644		}
```

The `→` marker alone means "this is the line". When the agent has additional
diagnostic insight beyond just identifying the line (e.g. the value of a
variable, why the condition matters, what is NULL), append it as an inline
comment using `// ←`:

```
→  643			kref_get(&kobj->kref);   // ← kref already 0; object freed
```

Both the `→` prefix and the `// ←` comment may appear on the same line.
Inline `// ←` comments are agent annotations and must **not** be given a
line-number prefix.


### Inlined functions and macros

The source file and line number returned by `gdb` or `addr2line` may point
inside an inlined function or a macro expansion rather than directly to the
backtrace function itself. Apply these rules:

**Inlining:** If the resolved source line is inside a *function* that was
inlined into the backtrace function (i.e., `gdb` reports it in a different
`.c` or `.h` file), show the inlined function — not the outer (backtrace)
function. The compiler moved the code there; the inlined function is what
actually executed at that point.

Example: `rcu_do_batch+0x1bc` resolves to `arch/x86/include/asm/preempt.h:27`
because `preempt_disable()` was inlined into `rcu_do_batch`. Report the
inlined function from `preempt.h`, not `rcu_do_batch` itself for that offset.

**Macros:** If the function is *defined* via a macro (e.g.,
`DEFINE_IDTENTRY_SYSVEC(sysvec_apic_timer_interrupt)`), do **not** show the
macro definition. Instead, show the function body that the macro expands to —
i.e., treat the macro invocation as the function signature and list the
statements inside the generated function.

Example: `DEFINE_IDTENTRY_SYSVEC(sysvec_apic_timer_interrupt) { ... }` should
be reported as:
```c
  19 // defined via DEFINE_IDTENTRY_SYSVEC macro
  20 sysvec_apic_timer_interrupt(struct pt_regs *regs)
  21 {
  22    ...
  23 }
```


### Structs

If a struct is a key element of the crash (top entry in the backtrace, i.e. the crash site), for
example because a member of a struct gets dereferenced and is NULL, include
the definition of the struct in the output. Include the struct definition
even if a member of a struct is first assigned to a local variable and then
dereferenced.

Apply the same summarization rules (defined below for functions) to struct definitions longer than 20 lines.

### Functions ≤ 20 lines

Functions up to and including 20 lines in length should be listed as a whole.
Do not report this fact, it is obvious from the shown source.

Use the `→` prefix marker (described above) on the relevant line.
Add a `// ←` inline comment if there is additional diagnostic information to convey.

### Functions > 20 lines

Functions that are larger than 20 lines will need to be abbreviated using
the pattern described below.
Do not report this fact, it is obvious from the shown source.

Example:
```c
 23  void long_function(struct foo bar[])
 24  {
 25       int counter;
          ...
 47       if (counter < 40)
→ 48             bar[counter] = 0;
 49       else
          ...
 71  }
```
Key rules for summarization:
1. Retain the function signature and its opening and closing braces.
2. Retain any key local variable declarations that are relevant to the crashing line.
3. Add 1 to 2 lines of context before and after the crashing line.
4. Retain any special "if" statements that may impact the crashing line, including NULL or bounds checks.
5. Replace all other non-essential pieces with a `...` (as shown in the example above).
6. Lines replaced with "..." should not get line numbers.
7. Comment lines added by the agent as annotations (e.g. `// ← RBX = info = NULL`) should not get line numbers, since they are not part of the original source.
