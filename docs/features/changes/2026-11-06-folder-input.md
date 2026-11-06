# Change: Folder input   (2026-11-06)

## What changed
- F11 — Folder input (new): `pii-strip <folder>` redacts every PDF directly in the folder into `<folder>/processed/<name>-stripped.pdf`.
- F01 — Walking skeleton: `-o` is still required for a single file, but not allowed with a folder.
- F09 — JSON report: with a folder, one report holds one entry per file. The single-file report is unchanged.
- `docs/idea.md`: batch/directory processing moves from "out of scope (v1)" and "Not Doing" to a planned feature.

## Why
The developer wants to redact several documents in one run. The shell loop suggested in the idea needs an output name per file, and it loses the exit code of every file but the last.

## Impact (add / modify / remove)
- **Add:** folder mode in the CLI (file discovery, output naming, `processed/` folder, per-file messages prefixed with the file name, a final summary, the combined exit code); a folder report shape.
- **Modify:** argument checks (`-o` required only for a file, forbidden with a folder; `--force` applies per output file); the offline test (F10) also runs a folder; the README (usage, exit codes).
- **Remove:** the idea doc's "Batch or directory processing" out-of-scope bullet and the "Batch/directory mode" Not Doing bullet.

## Behavior to verify
- A folder with two PDFs, a `.txt` file, a subfolder and `.DS_Store` produces exactly two outputs in `processed/`, named `<name>-stripped.pdf`, and lists the `.txt` file and the subfolder as skipped.
- A second run without `--force` writes nothing new and exits with `1`; with `--force` it overwrites.
- With one corrupt PDF and one good PDF, the good output is written and the exit code is `1`.
- With one file that has PII left (`2`) and one with image-only pages (`3`), the exit code is `2`.
- `-o` with a folder exits with `1`.
- A folder without PDFs exits with `1`.
- `--report` writes one file with an entry per PDF and no matched text by default.
- Single-file runs behave exactly as before.

## Affected feature files
- `docs/features/F11-folder-input.md` (new)
- `docs/features/README.md` (index)
- `docs/idea.md`
