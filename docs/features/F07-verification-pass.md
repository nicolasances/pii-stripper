# F07 — Verification pass and exit code 2

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

After saving, the tool checks its own output: it reopens the PDF, extracts the text again and confirms that no redacted string and no detectable PII is left. If anything remains, it exits with code `2`.

This turns "I hope it worked" into something a developer and a script can rely on. A redaction tool that fails silently is worse than having no tool.

**Out of scope**:
- Checking image-only pages (F08)
- Fixing anything automatically on failure

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <input.pdf> -o <output.pdf>` | Verification always runs after saving |
| Exit code | — | `2` | Verification found PII left in the output |

### Endpoint: `pii-strip <input.pdf> -o <output.pdf>`
**Description:** Runs the verification after saving and sets the exit code from the result.

**Expected Use Case:** A developer, or a script wrapping the tool, needs to know whether the output is safe to share without inspecting it manually (US-05).

## 4. Business Logic

- After saving, the output file is reopened from disk (not from memory) and its text is extracted again.
- **Check 1, residual strings:** none of the strings that were redacted may appear in the output text (case-insensitive).
- **Check 2, residual findings:** detection runs again on the output with the same configuration (languages, entities, threshold, deny and allow lists). Every finding is a residual.
- If either check finds anything, a message goes to stderr naming the entity type and page of each residual (the text itself only in a form that doesn't leak it, see OQ-01), and the exit code is `2`.
- The output file is **still written** on failure, so the developer can inspect it. The message says plainly that it isn't clean.
- If both checks pass, the exit code is `0` (unless F08 sets `3`).
- If both `2` and `3` apply, `2` takes precedence: leaked PII is worse than unchecked pages.
- Verification can't be turned off.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Reopen from disk instead of reusing the in-memory document | Verifies what is actually in the file, including the save step |
| TD-02 | Keep the output on failure | Developers need to see what went wrong; the exit code and message prevent misuse |
| TD-03 | Verification is always on | It's cheap for typical document sizes, and the guarantee matters most |
| TD-04 | The residual-string check is case-insensitive and whole-word, and whitespace inside a string also matches a line break | Same matching as the redaction and the deny list, so `An` isn't reported inside `Anbefalinger`. Note: a detected word such as `With` is only redacted where its case matches, so a lowercase `with` elsewhere is reported as a residual. This errs on the safe side |
| TD-05 | `redact_pdf` fills an optional `redacted` list with every detected string and its entity type (`RedactedString`), also when no area was found on the page. Verification lives in `verify.py` and the CLI calls it after saving | Same pattern as `counts` in F06. Recording detected strings, not redacted areas, is what lets verification catch strings the search missed |
| TD-06 | Residuals are reported once per entity type and page | A list of `PERSON on page 2` lines is enough to know where to look |
| TD-07 | Known names and their parts (F04 TD-05) are added to the redacted strings with `exact_case`, and are only reported in the same case or in capitals | They are redacted with that rule, so a lowercase `skov` for the surname `Skov` must not fail the run |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | A clean run exits with `0` | |
| SC-02 | When redactions aren't applied (simulated in a test by substituting the redaction step), the run exits with `2` and names the remaining items on stderr | |
| SC-03 | A string the tool can't redact (e.g. split across lines in a way searching misses) is reported as a residual | Documents the known limitation from F01 |
| SC-04 | The output file exists after a run with exit code `2` | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | How should residuals be shown on stderr without leaking them into logs? | **Resolved:** entity type and page only (`EMAIL_ADDRESS on page 2`). No text, not even masked |
| OQ-02 | Should a failed verification delete the output instead? | **Resolved:** no, the output is kept (TD-02). The message says it is not clean and must not be shared |
