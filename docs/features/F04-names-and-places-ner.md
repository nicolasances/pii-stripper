# F04 — Names and places (Danish + English NER)

## 1. Purpose & Scope

Detect and redact person names and, optionally, places using named entity recognition (NER) models for Danish and English. Names are the most common PII in documents and can't be caught with patterns.

This feature carries the **project's biggest risk**: whether Danish NER finds enough names. It therefore includes a measurement of recall (the share of names actually found) on synthetic documents. That result is the go/no-go input for the model choice.

**Out of scope**:
- Danish street addresses (OQ-02 in `docs/idea.md`)
- Organization names (usually not personal data)
- LLM-based detection

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <input.pdf> -o <output.pdf>` | Also detects `PERSON` and, if enabled, `LOCATION` |
| CLI flag | — | `--lang da,en` | Languages to analyze with (default: `da,en`) |
| CLI flag | — | `--entities PERSON,DK_CPR,...` | Restrict detection to the listed entity types (default: all supported entity types, see OQ-01) |
| Dev command | — | recall check script (e.g. `uv run scripts/recall_check.py`) | Generates synthetic documents, runs detection, prints recall per entity type |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf> [--lang] [--entities]`
**Description:** Each page's text is analyzed with every language listed, and the results are merged before redaction.

**Expected Use Case:** A developer redacts a mixed Danish/English document with names in the body text, signatures and headers (US-03).

### Endpoint: recall check (developer tool, not shipped in the CLI)
**Description:** Builds about 10 synthetic documents with known PII positions (Faker `da_DK` and `en`), runs detection and prints recall and precision per entity type.

**Expected Use Case:** The developer decides between spaCy and DaCy for Danish NER, and tunes default scores and thresholds.

## 4. Business Logic

- The detection framework is configured with an **explicit** NLP setup: a Danish model for `da` and an English model for `en`. No implicit default model is ever loaded.
- Pattern recognizers from F01–F03 are registered for every configured language, so they fire whichever language is being analyzed.
- Each page is analyzed once per language. Overlapping findings from different languages are merged into one finding with the highest score; non-overlapping findings are combined.
- `PERSON` is enabled by default. Whether `LOCATION` is enabled by default is decided in this feature (see OQ-02).
- `--entities` limits detection to the listed types; an unknown entity type fails with exit code `1`.
- `--lang` accepts any subset of `da` and `en`; other values fail with exit code `1`.
- If a required model isn't installed, the tool fails with exit code `1` and a message saying how to install it. **It never tries to download a model itself.**

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Start with spaCy `da_core_news_*` and `en_core_web_*`; switch to DaCy only if the recall check shows Danish names are missed too often | spaCy is lighter and fits Presidio easily; DaCy is likely more accurate but heavier (transformer-based) |
| TD-02 | Pin the model packages as project dependencies | Reproducible installs and no download at runtime (offline guarantee, F10) |
| TD-03 | Run every language and merge, instead of detecting the document's language | Mixed-language documents are common; language detection per paragraph adds error. It costs roughly double the processing time, which is acceptable for ad hoc use |
| TD-04 | Recall check as a developer script, not a CLI command | It's an evaluation tool for the developer, not a user feature |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | Fixture PDFs with Danish and English names have the names redacted | Including names in headers and signatures |
| SC-02 | The recall check runs and prints recall and precision per entity type | |
| SC-03 | The recall check result for Danish `PERSON` is recorded, and a model decision (spaCy size or DaCy) is made and noted in this feature file | Go/no-go for the approach |
| SC-04 | A missing model fails with exit code `1` and install instructions, with no network access attempted | |
| SC-05 | `--lang en` analyzes only with the English model; `--entities` restricts the redacted types | |
| SC-06 | Processing a 10-page document takes under ~30 seconds on a developer laptop | A rough budget, to be adjusted after measuring |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Which spaCy model size (sm, md or lg), or DaCy? | Decided by SC-03 |
| OQ-02 | Should `LOCATION` be on by default? | Catches cities and places, but over-redacts public place names like "København" or "Aarhus" |
| OQ-03 | What is an acceptable recall for Danish `PERSON` in v1? | Suggestion: ≥ 0.85 on synthetic documents, with the deny list (F05) as the fallback |
| OQ-04 | How are names in all caps or in tables handled? | NER models often miss them; measure in the recall check |
| OQ-05 | Does Presidio register its built-in recognizers for `en` only? | Must be verified against the Presidio docs; it affects how the `da` configuration is set up |
