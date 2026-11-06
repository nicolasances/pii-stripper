# F04 — Names and places (Danish + English NER)

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

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
| TD-05 | Names are known document-wide (#21): every page is analyzed first, then each full `PERSON` name and its name parts are redacted on every page where they occur | The model often misses a name in a short snippet with no context, e.g. a surname alone in a footer. Knowingly over-redacts a common surname that belongs to someone else; the allow list is the remedy |
| TD-06 | A name part is a word of the name span that is capitalized, has at least 3 letters (hyphens allowed) and is not a salutation or title (`Kære`, `Dear`, `Hr`, `Vedr` …). A one-word name that is a salutation or title is not spread either | The model includes salutations and sentence starts in name spans (see the recall check notes), which must not be blacked out on every page. Initials are too short to identify anyone |
| TD-09 | Salutations and job titles (`Kære`, `Dear`, `Head`, `Chief`, `Direktør`, `Chef` …, one list in `nlp.NOT_NAME_WORDS`) are cut off the start and end of every `PERSON` span, and are never name parts | The model stretches a name over a following title without a comma: `Ryan Mendez Head of Innovation` is tagged `Ryan Mendez Head`. Without trimming, `Head` was blacked out there and, with TD-05, on every page. Recall on the recall check is unchanged |
| TD-07 | A known name is only redacted in the same case or in capitals, like every other redaction | Many Danish surnames are ordinary words (`Skov`, `Lund`, `Holm`); case-insensitive matching would black out `skov` everywhere |
| TD-08 | Known-name hits are `PERSON` findings with the source `known_name`, only where no other finding already covers the area | Tells propagated hits apart from the model's own in the report (F09), without counting the same area twice |

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

## 8. Implementation Notes

**Model decision (SC-03, OQ-01):** spaCy `da_core_news_md` and `en_core_web_md` (3.8.0), pinned in `pyproject.toml`. Run `python -m scripts.recall_check --seed N --show-misses` to reproduce. On 10 synthetic documents (5 Danish, 5 English, Faker `da_DK` / `en_US`), seeds 1-3, languages `da,en`:

| Entity | Recall | Precision |
|---|---|---|
| Danish `PERSON` | 1.00 on all three seeds | 0.61-0.67 |
| English `PERSON` | 0.90-0.95 | 0.95-1.00 |
| `LOCATION` (all) | 0.90-1.00 | 0.82-1.00 |

- Danish `PERSON` recall meets the ≥ 0.85 suggestion in OQ-03, so **DaCy is not needed on this evidence** and the medium spaCy models stay. Sizes `sm` and `lg` were not compared.
- The result comes from templated, synthetic text with easy Faker names. Real documents will be harder, so treat it as a lower bar, not proof. OQ-04 (names in all caps or in tables) was **not measured**.
- Danish precision is low: the model tags sentence starts such as `Vi har talt med` and `Vedr`, and includes salutations (`Kære Mette Hansen`, `Dear Ryan Mendez`) in the span. The name is still redacted, but so are the extra words. The allow list (F05) is the remedy.
- The recall check counts a name as found when a same-type finding contains it, and a finding as correct when it overlaps an expected one of the same type.
- A 10-page synthetic document took under 1 second (short pages, models already installed), well inside the SC-06 budget. Not measured on dense real pages.

**`LOCATION` default (OQ-02):** off. Enable it with `--entities PERSON,LOCATION,...`. The default entity set is `PERSON`, `EMAIL_ADDRESS`, `DK_CPR`, `DK_PHONE` and `SOCIAL_PROFILE`.

**`SOCIAL_PROFILE` (#21):** a pattern entity type, on by default, for profile URLs on LinkedIn (`linkedin.com/in/…`), Facebook, Instagram, X/Twitter, GitHub and TikTok (`tiktok.com/@…`), with or without the scheme and a `www.` or two-letter subdomain. The whole URL is redacted, not only the profile name. A platform without a profile and a LinkedIn company page are not matched. Bare `@handles` and other platforms are not detected.

**Design notes:**
- `nlp.build_analyzer` creates a Presidio `AnalyzerEngine` with an explicit `SpacyNlpEngine` (one model per requested language) and one `SpacyRecognizer` per language. Danish labels `PER` and `LOC` and English `GPE` map to `PERSON` and `LOCATION`; every other label is ignored.
- OQ-05 was sidestepped: the email, CPR and phone recognizers are language-independent and run once on the whole text, not registered per language in Presidio.
- Findings from different languages are merged per entity type (highest score wins). Overlapping findings of different types are kept apart.
- Two filters cut false positives from short snippets: an NER span that contains a digit or starts with a lowercase letter is dropped (the models tag `tlf` and `Nummer 0101901234`), and an NER span that overlaps an email, CPR or phone match is dropped so the pattern match wins. A consequence: a name directly followed by digits in the same span is not redacted as a name.
- `--lang` and `--entities` validation errors, and a missing model, exit with code 1. The model check runs before processing and only when `PERSON` or `LOCATION` is requested. Nothing is ever downloaded at runtime.
- The missing-model path is tested by faking `spacy.util.is_package`, not by cutting the network.
- **Company names are not redacted.** The English model often calls a bare company name a person (`Novo Nordisk`, `Tryg`), while the Danish model labels it `ORG`. Organization spans from either model are kept internally and used to drop a `PERSON` or `LOCATION` finding that overlaps one by at least 60% (`nlp.without_organizations`). Organizations themselves are never reported.
- The 60% rule exists because the English model also tags long stretches of Danish text as `ORG` (`Laus Thomsen fra Novo Nordisk om`). Dropping every overlap cost Danish `PERSON` recall (1.00 → 0.85-0.95) and `LOCATION` recall. With the rule, `PERSON` recall over all documents is 0.90-0.93 (seeds 1-3, before the rule 0.95-0.97).
- Known remaining miss: when the two models disagree on the same span (one says `PERSON`, the other `ORG`), the name is dropped. A real person called out as `ORG` by one model is therefore not redacted. The allow list and deny list (F05) are the remedy in both directions.
- Whole-word matching in the redactor: a detected string is redacted only where it appears as whole words, in the same case or in all capitals. This stops a false positive such as `An` or `With` from blacking out every `an` or `with` on the page.
