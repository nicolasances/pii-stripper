# F06 — Sanitize metadata, annotations and attachments

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

Remove PII from the parts of a PDF that aren't visible page text: document metadata, XMP metadata, annotations and comments, form fields, embedded files and bookmarks. These are routinely forgotten, and they leak PII even when the page text is clean.

**Out of scope**:
- Detecting PII inside the removed content (it's removed whole, not analyzed)
- Images embedded in the page content (covered by redaction areas only; image analysis is a future idea)
- JavaScript and other active content (see OQ-03)

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <input.pdf> -o <output.pdf>` | Sanitizing is always on |
| CLI flag | — | `--keep-outline` | Keep bookmarks/outline (removed by default) |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf> [--keep-outline]`
**Description:** After redaction, all hidden content is removed before saving.

**Expected Use Case:** A developer redacts a PDF that went through review (comments with reviewers' names), was exported from Word (author in metadata) or has attachments (US-04).

## 4. Business Logic

- Document metadata fields (title, author, subject, keywords, creator, producer, creation and modification dates) are cleared.
- XMP metadata is removed.
- All annotations are removed (comments, highlights, notes, links, stamps), apart from redaction marks that have already been applied.
- Form fields: decided in OQ-01. The default proposal is to **remove** them, values included.
- All embedded files and attachments are removed.
- Bookmarks/outline are removed unless `--keep-outline` is given.
- The file is saved with garbage collection and without incremental updates, so deleted objects can't be recovered from the file.
- Sanitizing is **always on**. There is no flag to turn it off, because a partial sanitize is a footgun.
- Every action is counted (e.g. number of annotations removed) and passed to the report (F09).

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Remove hidden content whole rather than analyzing it for PII | Simpler and safer; this content is rarely needed in a shared copy |
| TD-02 | Sanitizing can't be turned off | Removes a way to get it wrong |
| TD-03 | Bookmarks are removed by default, with an opt-out | Bookmark titles can contain names, but they're useful in long documents |
| TD-04 | Counts are a `SanitizeCounts` dataclass (`sanitize.py`). `redact_pdf` keeps returning the number of redacted areas and fills an optional `counts` argument | Avoids changing the return value before F09 defines the report |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | A fixture PDF with PII in metadata, XMP, a comment, a form field, an attachment and a bookmark produces an output where none of these remain | Generate the fixture programmatically |
| SC-02 | A search of the **raw bytes** of the output finds none of the PII strings from SC-01 | Proves that deleted objects didn't survive |
| SC-03 | With `--keep-outline`, the bookmarks remain | |
| SC-04 | The visible page content apart from the redactions is unchanged | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should form fields be removed or flattened? | **Resolved:** removed, values included. Flattening would need detection to run again afterwards |
| OQ-02 | Should link annotations to URLs be kept? | **Resolved:** no. All annotations are removed, links included |
| OQ-03 | Should JavaScript and other active content be removed as well? | **Open.** Not PII, but a good hygiene step for shared files. Not done in F06 |
| OQ-04 | Is the raw-byte check reliable when streams are compressed? | **Resolved:** the tests check the raw bytes and also decompress every object through the PDF library |
