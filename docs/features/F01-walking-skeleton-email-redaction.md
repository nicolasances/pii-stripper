# F01 — Walking skeleton: email redaction end to end

## 1. Purpose & Scope

This feature delivers the first working version of `pii-strip`. It reads a PDF, finds email addresses, **truly redacts** them (the text is removed from the file and a black box is drawn in its place) and writes a new PDF.

It also sets up the shared foundation every later feature builds on:
- the Python project, packaging and the `pii-strip` console command
- the detect → map to page areas → redact → save pipeline
- a generator for test PDFs containing synthetic (fake) PII
- consistent error handling and exit codes

Email is the first entity type because a single built-in pattern recognizer can detect it reliably. That proves the whole pipeline without involving NER models yet.

**Out of scope**:
- Every other entity type (CPR, phone, names, places): F02–F04
- Metadata or annotation cleanup: F06
- Verification of the output: F07
- Reports: F09

## 2. Key Endpoints

The "endpoint" of this tool is its command-line interface.

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command | — | `pii-strip <input.pdf> -o <output.pdf>` | Redact PII from the input PDF and write a new PDF |
| CLI flag | — | `--help` | Show usage, flags, exit codes and the "assistive, not a guarantee" disclaimer |
| CLI flag | — | `--version` | Print the tool version |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf>`
**Description:**
Reads the input PDF, detects email addresses on every page, removes them with true redaction and writes the result to the output path. It never modifies the input file.

**Expected Use Case:**
A developer has a PDF to attach to a bug report or use as a test fixture, and needs a copy with no personal contact details in it (US-01, US-02 in `docs/idea.md`).

**Behavior:**
- `-o/--output` is required. If the output path equals the input path, the command fails, so the tool never redacts in place.
- If the output file already exists, the command fails unless `--force` is given.
- Exit codes introduced here: `0` success, `1` error (input not found, not a PDF, encrypted or password-protected, output not writable). Error messages go to stderr.

## 4. Business Logic

- The input file is opened read-only and is never modified.
- The text of each page is extracted, and the PII detection framework is run on it with the email recognizer enabled.
- Every detected string is mapped to page areas by searching the page for that exact string. **Every occurrence** of the string on that page is redacted, even where the detector didn't flag it (deliberate over-redaction).
- A black-filled redaction mark is added for each area, and redactions are applied per page so the underlying text is **removed from the content**, not just covered.
- The output is saved as a new file with no incremental update, so the original text doesn't survive in older revisions inside the file.
- Text outside the redacted areas, the page layout and the page count stay unchanged.
- Encrypted or password-protected PDFs are rejected with exit code `1` and a clear message.
- The pipeline is structured so later features can add recognizers, sanitizing steps and post-save checks without restructuring it.
- Test fixtures are generated PDFs containing only synthetic PII. Real documents are never committed.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Python 3.11+, packaged with `uv` and `pyproject.toml`, exposed as the `pii-strip` console script | Python has the mature redaction and PII detection libraries; TypeScript lacks a mature true-redaction option (see `docs/idea.md` §8) |
| TD-02 | PyMuPDF for reading the PDF, finding text positions and applying redactions | One of the few open libraries that removes the underlying text as well as covering it. **AGPL**: fine internally; check with DR Jura before any external distribution |
| TD-03 | Microsoft Presidio (analyzer) as the detection framework | Gives a recognizer model, scoring and built-in recognizers that later features extend |
| TD-04 | Map findings to page areas by searching for the matched string on the page | Simplest approach. It over-redacts repeated strings, which is the safe failure mode for a PII tool (OQ-03 in `docs/idea.md`) |
| TD-05 | Use a lightweight CLI framework (e.g. Typer or argparse) | Standard, well-documented options; pick one at implementation time |
| TD-06 | Generate test fixtures with PyMuPDF, with fake data from Faker (`da_DK` and `en` locales) | Keeps real PII out of the repo and makes fixtures reproducible |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | Running the command on a fixture PDF containing email addresses produces an output in which no email address can be found by text extraction | Automated test |
| SC-02 | Non-PII text on the same page is still extractable from the output | Proves the redaction is precise enough |
| SC-03 | The output has the same number of pages as the input, and black boxes are visible where the emails were | Visual check plus page count in the test |
| SC-04 | The input file is byte-for-byte unchanged after the run | Automated test |
| SC-05 | A missing file, a non-PDF or an encrypted PDF exits with `1` and prints a message on stderr | Automated tests |
| SC-06 | Output path equal to input path, or an existing output without `--force`, is refused | Automated tests |
| SC-07 | `pii-strip --help` describes the usage and states that the output must be reviewed before it's shared | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Typer or argparse? | Typer is more ergonomic but adds a dependency; argparse is part of the standard library |
| OQ-02 | Should email addresses split across two lines be handled? | Likely missed when searching for the exact string. Accept as a known limitation in v1, with a test documenting it? |
| OQ-03 | Is `--force` needed, or should an existing output always be overwritten? | `--force` is safer |
