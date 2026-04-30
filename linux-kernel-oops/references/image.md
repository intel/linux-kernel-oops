# Transcribing an OOPS from a Screenshot or Image

Use this primitive when the user provides a screenshot, photo, or other image
file containing a kernel oops, rather than raw text.

**First: determine the image type.** Visually inspect (or use your vision
capability on) the image:
- If it shows **monospace terminal text** → follow [Text screenshot path](#text-screenshot-path)
- If it shows a **QR code** (black-and-white square grid) → follow [QR code path](#qr-code-path-linux-drm-panic-v610)

---

## Text screenshot path

### Step 1 — Transcribe the image to text

**Preferred tool: `marker_single`** (from the `marker-pdf` package). It
handles PNG/image files directly and produces clean Markdown, which is ideal
for terminal screenshots. Use `uv tool run` to run it in an isolated sandbox
without polluting the system Python environment:

```bash
uv tool run --from marker-pdf marker_single /path/to/oops.png \
    --output_dir /path/to/output/ \
    --output_format markdown \
    --force_ocr
```

`--force_ocr` ensures all text is OCR'd even when the image appears to
contain selectable text. The output file will be
`<output_dir>/<image_basename>/<image_basename>.md`.

If `uv` is not available, install marker-pdf with pip as a fallback:

```bash
pip install marker-pdf
marker_single /path/to/oops.png \
    --output_dir /path/to/output/ \
    --output_format markdown \
    --force_ocr
```

**Fallback:** If neither `uv` nor `pip` can install `marker-pdf`, use your
built-in vision capability to read and transcribe the image directly.
Be meticulous — preserve all hex values, register names, backtrace entries,
module lists, and `Code:` lines exactly.

---

## QR code path (Linux drm_panic, v6.10+)

Linux v6.10+ includes `drm_panic`, which displays a panic screen containing
a QR code. The QR code encodes the kernel log (kmsg) compressed with zlib.
QR support was added in v6.12; encoding changed in v6.14.

### Step 1 — Decode the QR code

Use `zbarimg` (from the `zbar-tools` system package) to read the QR code:

```bash
zbarimg --raw /path/to/oops.png
```

This outputs a URL such as:
```
https://kdj0c.github.io/panic_report#?a=x86_64&v=6.14.1&z=<numeric_data>
```
or (legacy v6.10–v6.13):
```
https://kdj0c.github.io/panic_report#?a=x86_64&v=6.12.0&zl=<legacy_numeric_data>
```

Parameters: `a`=architecture, `v`=kernel version, `z`=new encoding (v6.14+),
`zl`=legacy encoding (v6.10–v6.13).

### Step 2 — Decode and decompress

Use the local helper script `linux-kernel-oops/scripts/decode_panic_qr.py` (pure stdlib, no
extra dependencies):

```bash
python3 scripts/decode_panic_qr.py "<url_from_zbarimg>" > oops.txt
```

The script handles both the v6.14+ (`z=`) and legacy v6.10–v6.13 (`zl=`)
encodings automatically.

---

## Step 2 — Save raw transcription

Save the transcribed oops text as `oops.txt` in the archive directory before
proceeding with analysis. This preserves the source text for reference.

## Step 3 — Record image provenance

Copy the original image into the archive directory as `oops.png` or `oops.jpg`
(matching the image type — never use the original filename). Then add the
following rows to the **Key Elements** table:

- `IMAGE_SHA256` — SHA-256 hash linked to the image:
  `[<hash>](oops.png)` (relative Markdown link, since the image is in the
  same archive directory as the report)
- `IMAGE_FILE` — original filename or path

The archive directory for image-sourced oops reports is:
`reports/images/<IMAGE_SHA256>/` (relative to the project root), unless the
user specifies otherwise.

## Step 4 — Hand off to analysis flow

Before running the analysis flow, insert the image at the top of the report
(above the Key Elements table) so readers can see the original source at a
glance:

```markdown
## Source screenshot

![Kernel oops screenshot](oops.png)
```

Then proceed with the normal analysis starting from
[Classify the crash type](primitives.md#classify-the-crash-type), using the
transcribed text as the source.
