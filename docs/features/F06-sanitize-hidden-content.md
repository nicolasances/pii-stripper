# F06 — Sanitize metadata, annotations and attachments

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
| OQ-01 | Should form fields be removed or flattened? | Removing loses non-PII content; flattening keeps visible values, which then need redaction (requires running detection after flattening) |
| OQ-02 | Should link annotations to URLs be kept? | They're rarely PII, but URLs can contain email addresses or usernames |
| OQ-03 | Should JavaScript and other active content be removed as well? | Not PII, but a good hygiene step for shared files |
| OQ-04 | Is the raw-byte check reliable when streams are compressed? | Text in compressed streams won't show up in a raw byte search. Decompress before searching, or check via the PDF library |
