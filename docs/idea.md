# pii-strip

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Core Concepts](#2-core-concepts)
3. [Features](#3-features)
4. [Data Models](#4-data-models)
5. [Key User Stories](#5-key-user-stories)
6. [Constraints & Assumptions](#6-constraints--assumptions)
7. [Open Questions](#7-open-questions)
8. [Not Doing (and Why)](#8-not-doing-and-why)
9. [Ideas for Future Versions](#9-ideas-for-future-versions)

---

## 1. Purpose & Scope

### 1.1 What is this?

A local-only Python CLI that takes a PDF and writes a new PDF with personally identifiable information **permanently removed**. The text is deleted from the file, not just covered, and a black box marks each spot. It also strips PII from places outside the visible text (metadata, annotations, attachments), then checks its own output to confirm nothing detectable is left.

```
pii-strip input.pdf -o output.pdf [--report findings.json] [--deny extra-terms.txt]
```

It is built from existing libraries rather than custom detection or PDF code:

- **PyMuPDF**: text extraction with positions, real redaction, removal of metadata and annotations
- **Microsoft Presidio** (`presidio-analyzer`): the PII detection framework (recognizers, scoring, entity types)
- **spaCy** with Danish (`da_core_news_*`) and English (`en_core_web_*`) models: name and location detection (NER) inside Presidio
- Custom Presidio recognizers for Danish formats (CPR, Danish phone numbers)

### 1.2 Who is it for?

Developers at DR who need to share or reuse a PDF (sample documents, bug report attachments, test fixtures) without leaking personal data. They run it ad hoc from a terminal and are comfortable with flags, JSON output and exit codes.

### 1.3 What problems does it solve?

- **Fake redaction:** drawing black boxes over text (e.g. with pdf-lib, or by hand in a PDF editor) leaves the text in the file, where anyone can copy it out. This tool removes the text itself.
- **Hidden PII:** author names in metadata, reviewer comments in annotations, and embedded attachments are routinely forgotten.
- **Danish PII:** most off-the-shelf PII tools target English and don't recognize CPR numbers, Danish phone formats or Danish names.
- **Data stays local:** documents never leave the machine, so no third-party processing or DPA is needed.
- **No silent failures:** the tool re-checks its output and exits with a non-zero code if PII is still detectable.

### 1.4 Out of scope (v1)

- Scanned or image-only PDFs. These are detected and reported, but not redacted.
- Interactive review (`scan` → edit → `apply`).
- Replacing PII with placeholders or fake values.
- Input formats other than PDF.
- Batch or directory processing.

---

## 2. Core Concepts

| Term | Definition |
|---|---|
| PII | Personally identifiable information: data that identifies a person directly (name, CPR, email) or indirectly (address, phone). |
| True redaction | Removing text, and the image pixels under it, from the PDF content, so it can't be extracted. In PyMuPDF this is `add_redact_annot` followed by `apply_redactions`. |
| Fake redaction | Covering text with a shape while the text stays in the file. This is what the tool is built to avoid. |
| Recognizer | A Presidio component that detects one entity type, using regex, a deny list, NER or a combination of these. |
| Entity type | A category of PII, e.g. `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `DK_CPR`. |
| Finding | One detected piece of PII: entity type, matched text, page, position and confidence score. |
| Sanitize | Removing PII from outside the visible page text: document metadata, XMP, annotations, form fields, embedded files. |
| Verification pass | Extracting text from the output PDF again and re-running detection, plus checking that no redacted string can still be found in the output. |
| Image-only page | A page with no extractable text (typically a scan). It can't be checked or redacted in v1. |
| Deny list | A file of terms the user wants redacted whatever the detector thinks, e.g. known names. |
| Allow list | A file of terms that should never be redacted, e.g. "DR" or public figures, to cut false positives. |

---

## 3. Features

### 3.1 PII detection (Danish + English)

- Presidio `AnalyzerEngine` with an NLP engine configured for both `da` and `en` spaCy models.
- Each page's text is analyzed with both languages and the results are merged (overlapping findings are combined and the higher score is kept).
- Entity types in v1:
  - `PERSON` (NER)
  - `LOCATION` (NER; catches cities and places, but **not** reliably street addresses, see OQ-02)
  - `EMAIL_ADDRESS`, `IBAN_CODE`, `URL` (Presidio's built-in recognizers, registered for both languages)
  - `DK_CPR`: custom regex `DDMMYY-XXXX` (with or without the dash), with a date check. No modulus-11 check, because some CPR numbers issued since 2007 don't satisfy it.
  - `DK_PHONE`: custom regex for 8-digit Danish numbers with an optional `+45`/`0045` prefix and common groupings.
- A minimum score (`--threshold`, default about 0.5, to tune on test documents) filters weak findings.
- `--deny FILE` and `--allow FILE` add terms to always redact or never redact.

### 3.2 True redaction

- Each finding is mapped to rectangles on the page. Starting approach: `page.search_for(finding.text)` for each page, which redacts **every** occurrence of the string on that page. This over-redacts on purpose; for a PII tool, a false positive is cheaper than a leak.
- A redaction annotation (black fill) is added for each rectangle, then `apply_redactions()` runs on each page so the underlying text is removed.
- Image handling during redaction: use PyMuPDF's option to blank the image pixels under a redaction box. Check the exact parameter in the PyMuPDF docs.

### 3.3 Sanitize

- Clear the document metadata (author, title, subject, creator, producer, keywords) and the XMP metadata.
- Remove all annotations (comments, highlights, notes) apart from the redactions just applied.
- Remove form fields (widgets) or flatten them, see OQ-04.
- Remove embedded files and attachments.
- Optionally remove bookmarks/outline, which can contain names.
- Save with garbage collection and without incremental updates, so deleted objects don't survive in the file.

### 3.4 Verification pass

- Reopen the output PDF and extract its text again.
- Check 1: none of the redacted strings can still be found in the output text.
- Check 2: re-run detection on the output. Any finding counts as a residual.
- If either check finds something, print it to stderr and exit with code `2`. The output file is still written so the user can inspect it.

### 3.5 Image-only page detection

- A page with no extractable text that contains at least one image is flagged as `image_only`.
- The tool prints a warning naming the pages and exits with code `3` unless `--allow-image-pages` is passed, so a scanned document never looks clean when it hasn't been checked.

### 3.6 Report

- `--report FILE` writes a JSON report: input/output paths, findings (entity type, page, score, **a hash of the matched text, not the text itself**), sanitize actions, verification result and warnings.
- `--report-include-text` adds the matched text to the report for local debugging. The flag warns that the report itself then contains PII.
- A one-line summary always goes to stderr, e.g. `redacted 14 items on 3 pages (PERSON 9, DK_CPR 2, EMAIL 3); verification OK`.

### 3.7 Exit codes

| Code | Meaning |
|---|---|
| 0 | Success, verification passed |
| 1 | Error (bad input, encrypted PDF, I/O) |
| 2 | Verification found residual PII |
| 3 | Image-only pages found and not allowed |

---

## 4. Data Models

```python
from dataclasses import dataclass, field
from typing import Literal

EntityType = str  # e.g. "PERSON", "DK_CPR", "EMAIL_ADDRESS"

@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

@dataclass
class Finding:
    entity_type: EntityType
    text: str                 # never written to the report unless --report-include-text
    text_sha256: str
    page: int                 # 0-based
    score: float
    language: Literal["da", "en"]
    source: Literal["ner", "regex", "deny_list"]
    rects: list[Rect] = field(default_factory=list)

@dataclass
class SanitizeActions:
    metadata_cleared: bool
    xmp_cleared: bool
    annotations_removed: int
    widgets_removed: int
    embedded_files_removed: int
    outline_removed: bool

@dataclass
class Verification:
    passed: bool
    residual_strings: list[str]      # redacted strings still found in the output
    residual_findings: list[Finding] # new detections in the output

@dataclass
class Config:
    languages: list[str] = field(default_factory=lambda: ["da", "en"])
    entities: list[EntityType] | None = None   # None = all supported
    threshold: float = 0.5
    deny_terms: list[str] = field(default_factory=list)
    allow_terms: list[str] = field(default_factory=list)
    remove_outline: bool = True
    allow_image_pages: bool = False

@dataclass
class Report:
    input_path: str
    output_path: str
    tool_version: str
    config: Config
    findings: list[Finding]
    image_only_pages: list[int]
    sanitize: SanitizeActions
    verification: Verification
```

Pipeline:

```
open PDF ─▶ per page: extract text ─▶ analyze (da + en, merge, filter, +deny −allow)
        ─▶ map findings to rects ─▶ add redact annots ─▶ apply_redactions
        ─▶ sanitize ─▶ save (garbage collect, no incremental)
        ─▶ verify (re-open, re-extract, re-analyze) ─▶ report + exit code
```

---

## 5. Key User Stories

| # | As a user, I want to… | So that… |
|---|---|---|
| US-01 | run `pii-strip in.pdf -o out.pdf` and get a redacted copy | I can share a document without leaking personal data |
| US-02 | have redacted text truly removed from the file | nobody can copy or extract it from under the black box |
| US-03 | have Danish CPR numbers, phone numbers and names detected | the tool works on DR's real-world documents, not just English ones |
| US-04 | have metadata, comments and attachments removed | PII doesn't leak through parts of the PDF I didn't think about |
| US-05 | get a non-zero exit code if PII is still detectable after redaction | I don't trust a result that silently failed |
| US-06 | be warned about scanned/image-only pages | I don't assume a scanned page has been checked |
| US-07 | give a deny list of names I know are in the document | the tool catches names the NER model misses |
| US-08 | give an allow list (e.g. "DR", "Danmarks Radio") | common non-PII terms aren't blacked out everywhere |
| US-09 | get a JSON report without the PII text in it | I can see what was removed without creating a new leak |
| US-10 | run it fully offline once models are installed | no document content leaves my machine |

---

## 6. Constraints and Assumptions

**Assumptions**

- **Danish spaCy NER is good enough for names.** This is the riskiest assumption. Expect misses on lowercase names, names in tables and names that are rare or not Danish. *Check:* run on 5–10 synthetic documents with known PII and measure recall per entity type. If it's poor, try DaCy or a larger model before building anything else.
- **Presidio can run `da` and `en` side by side.** Danish isn't built in, and I believe many predefined recognizers are registered for `en` only, so they'd need to be registered again with `supported_language="da"`. *Check:* a spike against the Presidio docs on day one.
- **Over-redaction via `search_for` is acceptable.** Blacking out every occurrence of a detected string on the page is OK for developer use. *Check:* look at the results on the test set.
- **PyMuPDF's `apply_redactions` really removes text.** It's documented to; the verification pass also tests it on every run.
- **Most input PDFs are born-digital** (they contain text, not just scans).

**Constraints**

- **Local only.** No cloud APIs, no telemetry. spaCy models are downloaded once at install time. This follows DR's guideline on not processing PII in tools without a DPA.
- **License:** PyMuPDF is AGPL-3.0 (with a commercial license available from Artifex). That's fine for an internal developer tool. **Check with DR Jura before distributing it outside DR or running it as a service.** Presidio is MIT; spaCy and its models have their own licenses, which should be checked per model.
- **Python 3.11+**, packaged with `uv`/`pyproject.toml` and exposed as a `pii-strip` console script. Model downloads are large; document them in the README.
- **Test data must be synthetic.** Never commit real documents containing PII as fixtures. Generate test PDFs with fake names, CPR numbers etc. (e.g. with Faker's `da_DK` locale and PyMuPDF or reportlab).
- **The tool is assistive, not a guarantee.** The README and `--help` must say plainly that output should be reviewed before it's shared.

---

## 7. Open Questions

| # | Question | Options / Notes |
|---|---|---|
| OQ-01 | Which Danish NER model? | `da_core_news_sm/md/lg` (spaCy) vs DaCy (better accuracy, heavier). Decide after the recall test on synthetic documents. |
| OQ-02 | How do we detect Danish street addresses? | spaCy `LOC` catches cities, not "Emil Holms Kanal 20, 2300 København S". Options: a regex for street + number + 4-digit postal code + city name, a DAWA-based postal code list, or skipping addresses in v1. |
| OQ-03 | How should text be mapped to positions? | `search_for` (simple, over-redacts) vs mapping character positions to `get_text("words")` (precise, handles repeats correctly, more code). Start with `search_for`. |
| OQ-04 | Should form fields be removed or flattened? | Removing loses non-PII content. Flattening keeps the visible values, which then need detection and redaction like normal text. |
| OQ-05 | Should the default entity set include `LOCATION`? | It catches places, but over-redacts mentions of public places ("København", "Aarhus"). Possibly off by default, or use the allow list. |
| OQ-06 | How are encrypted or password-protected PDFs handled? | Fail with code 1, or accept `--password`. |
| OQ-07 | Should running both `da` and `en` be the default? | It doubles processing time. Fine for ad hoc use; revisit if it's slow. |
| OQ-08 | Which CPR formats should be matched? | `DDMMYY-XXXX`, `DDMMYYXXXX`, `DDMMYY XXXX`. Need to watch for false positives on other 10-digit numbers. |

---

## 8. Not Doing (and Why)

- **TypeScript implementation:** the TypeScript ecosystem lacks a mature true-redaction option apart from `mupdf` WASM (also AGPL), and local NER there is weaker. Python gets us a working tool much faster.
- **OCR for scanned pages:** a big jump in complexity (Tesseract, image-region redaction, OCR errors). v1 detects and flags these pages instead of pretending to handle them.
- **Local LLM detection:** possibly better recall, but slow, non-deterministic and a heavy dependency. Revisit only if NER plus a deny list falls short.
- **Interactive review (`scan`/`apply`):** the `--report` data model is designed so this is a small v2 addition. It isn't needed for the first version.
- **Placeholders or fake replacement values:** text can't be cleanly replaced inside a PDF without breaking the layout. Black boxes are the honest output.
- **Batch/directory mode:** a shell loop (`for f in *.pdf; ...`) is enough for ad hoc use.
- **Non-PDF formats:** keep the scope narrow.
- **Guaranteeing completeness:** no detector catches all PII. The tool makes no such claim; it gives verification and a report.

---

## 9. Ideas for Future Versions

- **`scan` → edit `findings.json` → `apply`:** human-in-the-loop review in a text editor, built on the existing report model.
- **OCR support:** Tesseract (via PyMuPDF's OCR integration or `pytesseract`) for image-only pages, redacting the image regions.
- **Image redaction:** detect faces or signatures in embedded images.
- **Precise text-to-position mapping:** character-level mapping so only the detected occurrence is redacted.
- **More Danish recognizers:** CVR (when linked to sole proprietorships), license plates, Danish addresses via a DAWA postal code list.
- **Consistent pseudonymised text export:** `--text-out` writes plain text with `[PERSON_1]`, `[CPR_1]` etc., useful for test data and LLM-safe excerpts.
- **Pre-commit hook / CI check:** fail if a committed PDF contains detectable PII.
- **Evaluation harness:** synthetic document generator plus recall/precision metrics per entity type, to compare models.
