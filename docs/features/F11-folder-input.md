# F11 — Folder input

![Status](https://img.shields.io/badge/status-implemented-brightgreen?style=flat-square)

## 1. Purpose & Scope

Let the developer pass a folder instead of a single PDF. Every PDF directly in the folder is redacted, and each result is written to a `processed` subfolder as `<uuid>.pdf`, with a key file per PDF in a `keys` subfolder (#25). The same detection, sanitizing, verification and report rules as for a single file apply to each file.

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
| CLI flag (modified) | — | `--force` | No effect with a folder (#25) |
| CLI flag (modified) | — | `--report <file.json>` | With a folder: one JSON file with one entry per processed PDF |
| CLI output (modified) | — | stderr | Summary line and warnings per file, prefixed with the file name; a list of skipped files |
| Exit code (modified) | — | `0`–`3` | With a folder: the most serious result over all files |

### Endpoint: `pii-strip <folder> [options]`
**Description:** Processes every PDF directly in the folder, one after the other, with the same options for each. Each PDF gets a new random UUID; its output is `<folder>/processed/<uuid>.pdf` and its key file is `<folder>/keys/<uuid>.md`. Both folders are deleted and recreated at the start of every run.

**Expected Use Case:** A developer has a folder of documents to share (e.g. case files for a vendor or a bug report) and wants them all redacted in one run, with one place to collect the results and one exit code to check.

## 4. Business Logic

- **Folder or file:** if the input path is a folder, folder mode is used; otherwise the single-file behavior is unchanged.
- **Which files:** every regular file directly in the folder whose name ends in `.pdf`, ignoring case (`.pdf`, `.PDF`). Files are processed in name order.
- **Skipped entries:** subfolders and files that don't end in `.pdf` are not processed. They are listed on stderr in one warning. Hidden files (names starting with `.`, e.g. `.DS_Store`) and the `processed` and `keys` folders are skipped without a warning, so a second run isn't noisy.
- **No PDFs:** a folder without any PDF fails with exit code `1` and a message saying so. A folder that doesn't exist fails with exit code `1` as a missing input does today.
- **Output name (#25):** `<uuid>.pdf`, with a new random (v4) UUID per PDF and per run, so the output name can't give the person away.
- **Key file (#25):** `keys/<uuid>.md` holds the UUID, the candidate, the original file name, the redacted file (`processed/<uuid>.pdf`), the time of processing (UTC) and the result (`clean`, `personal data left (2)`, `image-only pages (3)` or `failed (1)`). A file that failed gets a key file but no output. `keys/` holds personal data and must not be shared with `processed/`.
- **`-o` with a folder** is a usage error (exit code `1`), so a user can't expect a different output location.
- **Re-runs (#25):** at the start of every run, before any file is processed, `processed/` and `keys/` directly inside the input folder are deleted and recreated, without `--force`; a warning names the deleted folders. Nothing else is deleted. If either name is a symbolic link or a file, the run fails with exit code `1` before deleting anything. `--force` has no effect in folder mode.
- **Per-file errors** (corrupt, encrypted, not writable) fail only that file (result `1`). The run continues with the next file.
- **Output per file:** the summary line, warnings (image-only pages, PII left, report text) and errors are printed per file, each prefixed with the input file name. `--quiet` suppresses the summary lines as for a single file.
- **Final summary:** after the last file, one line says how many files were processed and how many ended with each non-zero result. It is suppressed by `--quiet` unless a file failed.
- **Exit code:** the most serious result over all files, in this order: `2` (PII left in an output) > `1` (a file failed) > `3` (image-only pages not accepted) > `0`. A `2` must never be hidden by another result, because it means an output must not be shared.
- **Report:** with `--report <file.json>`, one JSON file is written with the tool, run time, configuration and the final exit code at the top level, and a list with one entry per processed PDF. Each entry holds the same per-file content as the single-file report (F09), but names the file by its UUID (`id`) instead of its input path (#25): output path, findings, image-only pages, sanitize counts, verification result and the file's own exit code. A file that failed with an error is listed with its result `1` and the error message, with the input path and file name in it replaced by the UUID. The hashing and `--report-include-text` rules of F09 are unchanged.
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
| TD-06 | A folder report has `schema_version` `2` and a `files` list of per-file entries; the single-file report keeps `schema_version` `1` | Existing consumers of the single-file report keep working, and a consumer can tell the two layouts apart by the version |
| TD-07 | A per-file entry has the same content as the single-file report (UUID and output path, start time, findings, image-only pages, sanitize counts, verification, exit code) plus `error`. A failed file has its error message and `verification` `null` | One shape to read per file; a failed file is visibly different from a clean one |
| TD-08 | The final summary line counts files per result, e.g. `processed 3 files: 1 clean, 1 with personal data left (2), 1 failed (1)` | One place to see the outcome of a long run |
| TD-09 | Outputs are named with a random UUID, and the link to the original file and candidate is kept only in `keys/` (#25) | Input files are often named after the person (e.g. a recruitment export); the redacted folder must not identify anyone. One place holds the link, so it can be kept apart from what is shared |
| TD-10 | Every run deletes and recreates `processed/` and `keys/`, without `--force` (#25) | Random UUIDs never clash, so outputs from earlier runs would pile up with duplicate keys. Deleting is limited to those two folders, and a symbolic link stops the run, so it can't reach anything else |

## 6. Success Criteria

| # | Criterion | Notes |
|---|-----------|-------|
| SC-01 | `pii-strip <folder>` writes `processed/<uuid>.pdf` and `keys/<uuid>.md` for every PDF in the folder, with PII removed | Synthetic fixtures only |
| SC-02 | Subfolders and non-PDF files are not processed and are listed as skipped; hidden files are skipped silently | |
| SC-03 | A second run replaces `processed/` and `keys/` without `--force`; nothing else is deleted | Changed by #25 |
| SC-04 | A corrupt PDF in the folder fails only that file; the other files are written | |
| SC-05 | The exit code is `2` if any output has PII left, even if another file failed or had image-only pages | |
| SC-06 | `--report` writes one JSON file with one entry per PDF, without the matched text by default | |
| SC-07 | `-o` together with a folder exits with `1` and explains why | |
| SC-08 | The offline test (F10) covers a folder run | |

## 7. Open Questions

| # | Question | Notes |
|---|----------|-------|
| OQ-01 | Should the report be allowed inside `processed/`? | **Resolved:** yes. It isn't a PDF, so a later run never picks it up; only the input and output PDFs are forbidden as the report path |
