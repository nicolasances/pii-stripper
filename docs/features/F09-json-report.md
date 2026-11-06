# F09 — JSON report and summary line

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

Tell the developer what happened in each run. A one-line summary always goes to stderr. An optional JSON report lists every finding, every sanitize action and the verification result, **without** writing the PII itself, so the report can't become a new leak.

The report format is also the basis for a later interactive `scan` → edit → `apply` workflow (`docs/idea.md` §9).

**Out of scope**:
- Reading a report back in to drive redaction (future `apply` command)
- HTML or PDF reports

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI output (modified) | — | stderr summary line | Always printed: counts per entity type, pages, verification status |
| CLI flag | — | `--report <file.json>` | Write the JSON report |
| CLI flag | — | `--report-include-text` | Also write the matched text into the report (prints a warning) |
| CLI flag | — | `--quiet` | Suppress the summary line (warnings and errors are still printed) |

### Endpoint: `pii-strip <in> -o <out> --report findings.json`
**Description:** Writes a JSON report next to the redacted PDF.

**Expected Use Case:** A developer wants to see what was redacted and why, or keep an audit trail of what was removed from a shared document (US-09).

## 4. Business Logic

- **Summary line** (stderr), for example: `redacted 14 items on 3 pages (PERSON 9, DK_CPR 2, EMAIL_ADDRESS 3); sanitized: 4 annotations, metadata; verification OK`.
- **Report contents:**
  - tool version, input and output paths, time of the run
  - effective configuration (languages, entities, threshold, deny and allow file paths, not their contents)
  - findings: entity type, page, score, language, source (NER, pattern, deny list, known name), page areas, and a **SHA-256 hash of the matched text**
  - image-only pages (F08)
  - sanitize actions and counts (F06)
  - verification result and residuals, with the same text rules as findings (F07)
  - the final exit code
- **By default the report contains no matched text.** The hash lets a developer check whether a specific value was redacted (hash it and search the report) without the report revealing it.
- With `--report-include-text`, the matched text is included and a warning is printed that the report itself now contains PII and mustn't be shared.
- The report is written even when the exit code is `2` or `3`. It isn't written when the run fails with exit code `1` before processing.
- The report's JSON schema has a version field, so later versions (e.g. `apply`) can rely on it.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Hash matched text with SHA-256 by default | Makes the report safe to keep or share while still allowing a lookup |
| TD-02 | Unsalted hash, except for CPR numbers, which get `"sha256": null` | Lets a developer check "was X redacted?". CPR numbers have a small value space and could be brute-forced from a hash (OQ-01) |
| TD-03 | Summary on stderr, not stdout | Leaves stdout free for future machine-readable output |
| TD-04 | `redact_pdf` fills an optional `findings` list with one `Finding` per distinct string per page (entity type, page, score, language, source, areas) | Same out-parameter pattern as `counts` (F06), `redacted` (F07) and `image_only_pages` (F08) |
| TD-05 | Source is `ner`, `pattern`, `deny_list` or `known_name` (a name found as `PERSON` on another page or elsewhere on the same page, F04 TD-05); language is the model that found a name, `null` for patterns and the deny list | NER results are tagged with their language before the cross-language merge, so the kept result keeps its language |
| TD-06 | The summary counts redacted areas, not distinct strings, and the pages that have at least one area | A string found but missed by the redaction search is reported by the verification instead |
| TD-07 | Residuals in the report have only the entity type and page | `Residual` never held text (F07), so it can't leak, even with `--report-include-text` |
| TD-08 | The report path may not be the input or output file; `--report-include-text` without `--report` is a usage error (exit `1`) | Avoids overwriting the PDF with JSON and silently ignored flags |
| TD-09 | If the report can't be written, the exit code is `1`, or `2` if PII is left in the output | `2` ("don't share the output") is the more important signal |
| TD-10 | An existing report file is overwritten, without `--force` | The report is a by-product of the run, not the user's document |
| TD-11 | A folder run (F11) writes a different layout with `schema_version` `2`: the per-file content of this report becomes one entry per file in a `files` list | The single-file report stays at version `1`, so existing consumers keep working |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | With `--report`, a valid JSON file with all listed sections is written | Snapshot or schema test |
| SC-02 | By default, none of the fixture's PII strings appear anywhere in the report file | Automated test searching the file |
| SC-03 | With `--report-include-text`, the matched text is present and a warning is printed | |
| SC-04 | The summary line is printed by default and suppressed by `--quiet` | |
| SC-05 | A report is written for runs ending with exit code `2` or `3` | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Is an unsalted hash acceptable? | **Resolved:** unsalted for all entity types except CPR numbers, whose hash is left out (TD-02) |
| OQ-02 | Should a JSON Schema file be published in the repo? | Useful for the future `apply` command |
