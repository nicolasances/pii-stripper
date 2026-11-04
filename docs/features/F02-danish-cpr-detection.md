# F02 — Danish CPR number detection

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

Detect and redact Danish CPR numbers (personal identification numbers). These are among the most sensitive PII in Danish documents, and generic PII tools don't recognize them.

**Out of scope**:
- Validating that a CPR number actually belongs to a real person
- CVR numbers (company registration numbers)
- Other Nordic national ID formats

## 2. Key Endpoints

No new command or flag. The existing `pii-strip <input.pdf> -o <output.pdf>` command (F01) now also redacts CPR numbers.

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <input.pdf> -o <output.pdf>` | Also detects and redacts the `DK_CPR` entity type |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf>`
**Description:** Same behavior as F01, with an additional recognizer for the `DK_CPR` entity type.

**Expected Use Case:** A developer redacts a Danish document (a letter, form or case file) that contains CPR numbers (US-03 in `docs/idea.md`).

## 4. Business Logic

- Formats recognized: `DDMMYY-XXXX`, `DDMMYYXXXX` (10 contiguous digits) and `DDMMYY XXXX`.
- The first six digits must form a valid calendar date (day 01–31 valid for the month, month 01–12; leap years handled for 29 February, with the century taken as 1900 or 2000).
- The **modulus-11 checksum is not used**: some CPR numbers issued since 2007 don't satisfy it.
- The match must have word boundaries, so a CPR-shaped substring inside a longer number doesn't match.
- Contiguous 10-digit matches get a lower confidence score than matches with a dash or space, because they collide with other long numbers (phone plus extension, account numbers). The score can be raised when context words appear nearby: "CPR", "cpr-nr", "personnummer", "fødselsdato".
- The entity type is reported as `DK_CPR`.
- The recognizer applies to both Danish and English text.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Implement as a custom Presidio pattern recognizer with a validation step and context words | Fits the framework from F01; context words are a built-in Presidio mechanism |
| TD-02 | No modulus-11 check | Would cause false negatives on valid modern CPR numbers |
| TD-03 | Lower base score for undelimited 10-digit matches | Balances recall against false positives; the threshold is tunable in F05 |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | A fixture PDF with CPR numbers in all three formats has all of them redacted | Synthetic CPR numbers only |
| SC-02 | Numbers with an invalid date (e.g. `320199-1234`, `011399-1234`) are not detected | Unit tests on the recognizer |
| SC-03 | Other 10-digit numbers without a valid date part are not detected | e.g. `9999999999` |
| SC-04 | A CPR number that fails the modulus-11 check but has a valid date is still detected | |
| SC-05 | A CPR-shaped substring inside a longer digit string is not detected | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should the 7th digit be used to resolve the century (the official rules) for the date check? | More accurate leap-year handling, but more complexity for little gain |
| OQ-02 | Should partial or masked CPR numbers (`010190-XXXX`) be redacted too? | The birth date alone is still personal data |
| OQ-03 | What score should undelimited matches get without context words? | Tune against the recall check in F04 |
