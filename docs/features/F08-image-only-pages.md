# F08 — Image-only page detection and exit code 3

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

Find pages that can't be checked because they contain no extractable text, typically scanned pages. Warn about them and exit with code `3`, so a scanned document never looks clean when it hasn't been checked.

**Out of scope**:
- OCR or redacting text inside images (future version)
- Detecting PII in images on pages that also contain text

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <input.pdf> -o <output.pdf>` | Flags image-only pages |
| CLI flag | — | `--allow-image-pages` | Accept image-only pages: warn, but don't change the exit code |
| Exit code | — | `3` | Image-only pages found and not allowed |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf> [--allow-image-pages]`
**Description:** Each page is classified before redaction. Image-only pages are listed in a warning.

**Expected Use Case:** A developer runs the tool on a PDF that turns out to be partly or fully scanned and needs to know that those pages weren't redacted (US-06).

## 4. Business Logic

- A page is **image-only** when it has no extractable text (after trimming whitespace) and contains at least one image.
- A completely empty page (no text, no images) isn't flagged.
- A page with very little text and a large image (e.g. a scan with a typed header) isn't flagged (OQ-01).
- Image-only pages are listed (1-based page numbers) in a warning on stderr.
- Without `--allow-image-pages`, the exit code is `3` if any page is image-only. With the flag, the warning is still printed but the exit code isn't affected.
- Exit code `2` (F07) takes precedence over `3`.
- The output is always written. The image-only pages are passed through unchanged.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Flag pages instead of trying OCR | OCR is a big jump in complexity; flagging is honest and cheap |
| TD-02 | Fail by default and allow an explicit opt-in | The safe default for an unattended run |
| TD-03 | `redact_pdf` fills an optional `image_only_pages` list with the page numbers (from 1), and the CLI prints the warning and sets the exit code | Same pattern as `counts` (F06) and `redacted` (F07); the page is classified while it is already open for redaction |
| TD-04 | The warning is also printed when the exit code is `2` | Both problems are worth knowing about; only the exit code follows the precedence |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | A fixture with two text pages and one image-only page warns about that page and exits with `3` | The image page can be a rendered image of synthetic text |
| SC-02 | The same fixture with `--allow-image-pages` exits with `0` and still warns | |
| SC-03 | Empty pages aren't flagged | |
| SC-04 | Text pages in the same document are still redacted normally | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should pages that are "mostly image" (little text, large image area) be flagged? | **Deferred:** only pages with no text at all are flagged for now. A coverage heuristic (e.g. > 80% image and fewer than N words) can be added later |
| OQ-02 | Should image-only pages be blanked or removed with a flag (`--drop-image-pages`)? | Gives a safe output without OCR |
