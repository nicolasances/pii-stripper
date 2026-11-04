# F03 — Danish phone number detection

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

Detect and redact Danish phone numbers in the formats commonly written in Danish documents. Generic phone recognizers often miss Danish groupings or confuse them with other numbers.

**Out of scope**:
- International numbers other than Danish (`+45`). Presidio's generic phone recognizer may still catch some; see OQ-01.
- Phone extensions and switchboard notation

## 2. Key Endpoints

No new command or flag. The existing `pii-strip` command (F01) now also redacts Danish phone numbers.

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <input.pdf> -o <output.pdf>` | Also detects and redacts the `DK_PHONE` entity type |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf>`
**Description:** Same behavior as F01, with an additional recognizer for the `DK_PHONE` entity type.

**Expected Use Case:** A developer redacts documents with contact details, such as email signatures, contact lists or letters (US-03).

## 4. Business Logic

- A Danish phone number is 8 digits, optionally prefixed with `+45`, `0045` or `(+45)`.
- Groupings recognized: `12345678`, `12 34 56 78`, `1234 5678`, `12-34-56-78`, and the same with a prefix.
- Matches need word boundaries and must not be part of a longer digit string.
- Context words raise the score: "tlf", "tlf.", "telefon", "mobil", "phone", "tel", "mob".
- A bare 8-digit number without a prefix or context gets a low score, because it collides with dates (`01012024`), amounts and IDs.
- 8 digits that form part of a detected CPR number are not reported as a phone number.
- The entity type is reported as `DK_PHONE`.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Custom Presidio pattern recognizer with context words | Same approach as F02 |
| TD-02 | Low base score for bare 8-digit numbers | The main source of false positives; tunable via the threshold in F05 |
| TD-03 | Resolve overlaps with CPR in favor of `DK_CPR` | A CPR number contains a valid-looking 8-digit run |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | A fixture PDF with phone numbers in every listed format, with and without a prefix, has all of them redacted | |
| SC-02 | Dates written as 8 digits and amounts like `12.345.678` aren't redacted at the default threshold | Unit tests |
| SC-03 | A CPR number is reported once, as `DK_CPR`, never as `DK_PHONE` | |
| SC-04 | A bare 8-digit number next to "tlf." is redacted | Context-word boost |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should Presidio's generic `PHONE_NUMBER` recognizer also be enabled for foreign numbers? | Possibly more recall on mixed documents, at the cost of more false positives |
| OQ-02 | Should Danish premium and short numbers (e.g. 4-digit numbers, 70xx xx xx) be excluded? | Business numbers aren't personal data, but they're hard to tell apart from personal ones |

## 8. Implementation Notes

- Scores: a number with a `+45`, `0045` or `(+45)` prefix, or with a context word within 30 characters before it, scores 0.85. A bare number scores 0.3. Context words are matched case-insensitively at a word start, so `Hotel 12345678` gets no boost but `Telefonnr` does.
- The prefix is part of the match, so it is redacted together with the number.
- Matches must not touch other digits, and must not start or end inside a longer run of two-digit groups (`12 34 56 78 90` is not a phone number).
- A minimal default threshold of 0.5 now lives in `find_pii_strings` (`DEFAULT_THRESHOLD`). Without it, bare numbers would still be redacted. It also means a bare 10-digit CPR number without a context word is no longer redacted (F02, OQ-03). F05 will make the threshold configurable.
- Overlap with CPR is resolved in `detector.without_phone_overlapping_cpr`: a `DK_PHONE` result that overlaps a `DK_CPR` result is dropped. With the current patterns the overlap is rare, so this is mostly a safeguard.

