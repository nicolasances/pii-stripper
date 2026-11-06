# F11 — Folder input

## 1. Purpose & Scope

Let the developer pass a folder instead of a single PDF. Every PDF directly in the folder is redacted, and each result is written to a `processed` subfolder as `<name>-stripped.pdf`. The same detection, sanitizing, verification and report rules as for a single file apply to each file.

This replaces the shell loop (`for f in *.pdf; ...`) suggested in `docs/idea.md` §8, which is error-prone: it needs an output name per file and loses the exit codes of all but the last file.

**Out of scope**:
- Recursing into subfolders
- Input formats other than PDF (unchanged from v1)
- Choosing another output folder or name pattern
- Processing files in parallel
- Glob patterns or a list of several files as input

## 2. Key Endpoints

**Summary of Endpoints:**
| Endpoint Type | Method | Invocation | Description |
|---|---|---|---|
| CLI command (modified) | — | `pii-strip <folder>` | Redact every PDF in the folder into `<folder>/processed/` |
| CLI flag (modified) | — | `-o`, `--output` | Required for a single file; not allowed with a folder |
| CLI flag (modified) | — | `--force` | With a folder: overwrite existing files in `processed/` |
| CLI flag (modified) | — | `--report <file.json>` | With a folder: one JSON file with one entry per processed PDF |
| CLI output (modified) | — | stderr | Summary line and warnings per file, prefixed with the file name; a list of skipped files |
| Exit code (modified) | — | `0`–`3` | With a folder: the most serious result over all files |

### Endpoint: `pii-strip <folder> [options]`
**Description:** Processes every PDF directly in the folder, one after the other, with the same options for each. The output for `<folder>/<name>.pdf` is `<folder>/processed/<name>-stripped.pdf`. The `processed` folder is created if it doesn't exist.

**Expected Use Case:** A developer has a folder of documents to share (e.g. case files for a vendor or a bug report) and wants them all redacted in one run, with one place to collect the results and one exit code to check.

## 4. Business Logic

- **Folder or file:** if the input path is a folder, folder mode is used; otherwise the single-file behavior is unchanged.
- **Which files:** every regular file directly in the folder whose name ends in `.pdf`, ignoring case (`.pdf`, `.PDF`). Files are processed in name order.
- **Skipped entries:** subfolders (including `processed` itself) and files that don't end in `.pdf` are not processed. They are listed on stderr in one warning. Hidden files (names starting with `.`, e.g. `.DS_Store`) are skipped without a warning.
- **No PDFs:** a folder without any PDF fails with exit code `1` and a message saying so. A folder that doesn't exist fails with exit code `1` as a missing input does today.
- **Output name:** `<name>-stripped.pdf`, where `<name>` is the input file name without its extension. The extension is always written in lowercase.
- **`-o` with a folder** is a usage error (exit code `1`), so a user can't expect a different output location.
- **Existing output:** an output file that already exists in `processed/` is not overwritten unless `--force` is given. Without `--force`, that file fails with an error (result `1`) and the other files are still processed.
- **Per-file errors** (corrupt, encrypted, not writable) fail only that file (result `1`). The run continues with the next file.
- **Output per file:** the summary line, warnings (image-only pages, PII left, report text) and errors are printed per file, each prefixed with the input file name. `--quiet` suppresses the summary lines as for a single file.
- **Final summary:** after the last file, one line says how many files were processed and how many ended with each non-zero result. It is suppressed by `--quiet` unless a file failed.
- **Exit code:** the most serious result over all files, in this order: `2` (PII left in an output) > `1` (a file failed) > `3` (image-only pages not accepted) > `0`. A `2` must never be hidden by another result, because it means an output must not be shared.
- **Report:** with `--report <file.json>`, one JSON file is written with the tool, run time, configuration and the final exit code at the top level, and a list with one entry per processed PDF. Each entry holds the same per-file content as the single-file report (F09): input and output paths, findings, image-only pages, sanitize counts, verification result and the file's own exit code. A file that failed with an error is listed with its result `1` and the error message. The hashing and `--report-include-text` rules of F09 are unchanged.
- **Report location:** the report path may not be one of the input or output files. It may be inside the folder; it is then not processed because it doesn't end in `.pdf`.
- **Deny and allow lists**, `--lang`, `--entities`, `--threshold`, `--keep-outline` and `--allow-image-pages` apply to every file. Names found in one file (F04 TD-05) are not carried over to the next file.

## 5. Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TD-01 | Only the top level of the folder is processed | The user's request; recursion would need rules for mirroring subfolders and for nested `processed` folders |
| TD-02 | `-o` is not allowed with a folder; the output location is fixed to `processed/` | One predictable place for results; avoids writing outputs next to the inputs, where they would be picked up as inputs on the next run |
| TD-03 | The exit code is the most serious result, with `2` > `1` > `3` > `0` | Scripts check one code; "PII left in an output" is the result that must never be lost |
| TD-04 | All files are processed even if one fails | A corrupt file shouldn't block the other documents; each failure is reported |
| TD-05 | Known names are kept per file, not across files | Documents in a folder can be about different people; spreading names across files would over-redact further |
| TD-06 | A folder report has a list of per-file entries and a new `schema_version`; the single-file report is unchanged | Existing consumers of the single-file report keep working |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | `pii-strip <folder>` writes `processed/<name>-stripped.pdf` for every PDF in the folder, with PII removed | Synthetic fixtures only |
| SC-02 | Subfolders and non-PDF files are not processed and are listed as skipped; hidden files are skipped silently | |
| SC-03 | A second run without `--force` doesn't overwrite outputs and exits with `1`; with `--force` it overwrites them | |
| SC-04 | A corrupt PDF in the folder fails only that file; the other files are written | |
| SC-05 | The exit code is `2` if any output has PII left, even if another file failed or had image-only pages | |
| SC-06 | `--report` writes one JSON file with one entry per PDF, without the matched text by default | |
| SC-07 | `-o` together with a folder exits with `1` and explains why | |
| SC-08 | The offline test (F10) covers a folder run | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should the report be allowed inside `processed/`? | Probably yes; it isn't a PDF and doesn't affect later runs |
