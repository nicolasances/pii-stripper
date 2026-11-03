# F10 — Offline guarantee and README

## 1. Purpose & Scope

Guarantee, and prove with a test, that the tool processes documents **without any network access**. Document installation, usage, limitations and licensing in a README.

Documents with PII must never leave the developer's machine. This follows DR's guideline that PII must not be processed in tools without a DPA.

**Out of scope**:
- Packaging for distribution (PyPI, Homebrew)
- A Docker image

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (unchanged) | — | `pii-strip <input.pdf> -o <output.pdf>` | Must work with network access blocked |
| Documentation | — | `README.md` | Installation, usage, exit codes, limitations, licensing |
| Test | — | offline test in the test suite | Runs the full pipeline with network access blocked |

### Endpoint: `pii-strip` run offline
**Description:** All models and dependencies are installed ahead of time; nothing is fetched at runtime.

**Expected Use Case:** A developer works on a sensitive document and needs to know that no content can leave the machine (US-10).

## 4. Business Logic

- At runtime, the tool makes no network calls: no model downloads, no update checks, no telemetry.
- Models are installed with the package (pinned dependencies, F04). If a model is missing, the tool fails with install instructions instead of downloading it.
- If a Hugging Face–based model is used (e.g. DaCy), the tool runs in offline mode so only the local cache is used.
- **Offline test:** the test suite blocks network sockets for the duration of the test and runs the full pipeline on a fixture PDF with every feature enabled. Any connection attempt fails the test.
- **README contents:**
  - what the tool does, in two sentences
  - installation, including the model downloads and their approximate size
  - usage examples for every flag
  - exit codes `0`, `1`, `2`, `3` and what to do for each
  - a clear disclaimer: the tool is **assistive, not a guarantee**; always review the output before sharing it
  - known limitations: scanned pages, strings split across lines, Danish addresses, names the NER model misses
  - licensing: PyMuPDF is AGPL-3.0; check with DR Jura before distributing outside DR or running it as a service
  - test data: use synthetic PDFs only; never commit real documents
  - how to check offline behavior manually (run with Wi-Fi off)

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Prove offline behavior with an automated test that blocks sockets | A test is permanent; a manual check only proves one moment |
| TD-02 | Fail instead of downloading a missing model | Prevents a hidden network call; makes installation explicit |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | The offline test passes with network sockets blocked | Part of the regular test suite |
| SC-02 | A manual run with the network off on a fresh install (after model installation) succeeds | Run once, and note it in the README |
| SC-03 | The README covers every item listed under Business Logic | Reviewed by the developer |
| SC-04 | A missing model fails with exit code `1` and no network attempt | Shared with F04 SC-04 |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Do any of the libraries (PyMuPDF, Presidio, spaCy) have telemetry or update checks in current versions? | Not known; the offline test will reveal it |
| OQ-02 | Should the README be in Danish, English or both? | Developers at DR; English is probably fine |
