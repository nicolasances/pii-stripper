# F05 — Deny list, allow list and threshold

## 1. Purpose & Scope

Give the developer manual control over what gets redacted:
- **Deny list:** terms that are always redacted (e.g. names you know are in the document but the NER model misses)
- **Allow list:** terms that are never redacted (e.g. "DR" or public figures)
- **Threshold:** the minimum confidence score for a finding to be redacted

This is the cheap safety net for the NER risk in F04.

**Out of scope**:
- Regular expressions in deny or allow lists (plain terms only, see OQ-01)
- Saving settings in a config file

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI flag | — | `--deny <file>` | A text file with one term per line, always redacted |
| CLI flag | — | `--allow <file>` | A text file with one term per line, never redacted |
| CLI flag | — | `--threshold <0..1>` | Minimum score for a finding to be redacted (default 0.5, see OQ-02) |

### Endpoint: `pii-strip <in> -o <out> --deny names.txt --allow allow.txt --threshold 0.6`
**Description:** Deny terms are added as findings, allowed terms are removed from the findings, and findings below the threshold are dropped.

**Expected Use Case:** The developer runs the tool, sees that a name was missed (or that "DR" was blacked out everywhere), adds it to a list and runs it again (US-07, US-08).

## 4. Business Logic

- List files are UTF-8, one term per line. Blank lines and lines starting with `#` are ignored, and leading and trailing whitespace is trimmed.
- Matching is case-insensitive and on whole words.
- Every occurrence of a deny term is a finding with entity type `DENY_LIST`, source `deny_list` and score 1.0. Deny findings are never removed by the threshold.
- A finding whose matched text equals an allow term (case-insensitive) is removed. A finding that only *contains* an allow term is kept: "DR" is allowed, but "Jens Hansen, DR" stays redacted as a name.
- If a term is in both lists, the **deny list wins**. The safer choice beats the convenient one.
- The threshold applies to all non-deny findings. Values outside 0 to 1 fail with exit code `1`.
- A missing or unreadable list file fails with exit code `1`.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Deny terms implemented as a Presidio deny-list recognizer, or as plain text search after detection | Either works; choose at implementation time based on how matching across line breaks behaves |
| TD-02 | Deny wins over allow | For a PII tool, a false positive is cheaper than a leak |
| TD-03 | Plain text files, not YAML or JSON | The simplest format to edit and to version |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | A name the NER model misses is redacted when it's listed in `--deny` | Use a rare or invented name in the fixture |
| SC-02 | "DR" isn't redacted when listed in `--allow`, even if it was detected | |
| SC-03 | A term in both lists is redacted | |
| SC-04 | Raising the threshold reduces the number of redactions; a deny term is still redacted at threshold 1.0 | |
| SC-05 | A missing list file or an invalid threshold exits with `1` | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should the lists support regular expressions? | Powerful but easy to get wrong. Not in v1 |
| OQ-02 | What is the right default threshold? | 0.5 as a start; tune with the recall check from F04 |
| OQ-03 | Should a default allow list be shipped (e.g. "DR", "Danmarks Radio")? | Convenient, but it hides behavior from the user |
