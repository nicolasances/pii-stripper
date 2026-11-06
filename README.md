# pii-strip

`pii-strip` removes personal data (names, email addresses, Danish CPR and phone numbers, social profile URLs, and optionally places) from a PDF. It does a true redaction: the text is removed from the file and a black box is drawn in its place. Metadata, comments, form values, attachments and bookmarks are cleaned too.

> **Assistive, not a guarantee.** No detector finds all personal data. Always review the output before you share it.

Everything runs locally. The tool makes no network calls at runtime: no model downloads, no update checks, no telemetry (see [Offline guarantee](#offline-guarantee)).

## Installation

You need Python 3.11 or newer.

```bash
git clone https://github.com/nicolasances/pii-stripper.git
cd pii-stripper
python -m venv .venv
source .venv/bin/activate
pip install .            # or: pip install -e ".[dev]" to run the tests
```

`pip install` also downloads the two spaCy language models. They are pinned in `pyproject.toml` and fetched from the spaCy GitHub releases **at install time only**:

| Model | Language | Version | Size on disk |
|---|---|---|---|
| `da_core_news_md` | Danish | 3.8.0 | ~50 MB |
| `en_core_web_md` | English | 3.8.0 | ~50 MB |

The whole install, with PyMuPDF, Presidio and spaCy, needs a few hundred MB.

If a model is missing at runtime, `pii-strip` stops with exit code `1` and tells you how to install it. It never downloads a model itself. To install one by hand:

```bash
pip install https://github.com/explosion/spacy-models/releases/download/da_core_news_md-3.8.0/da_core_news_md-3.8.0-py3-none-any.whl
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl
```

No Hugging Face models are used, so no Hugging Face offline mode is needed.

## Usage

```bash
pii-strip <input.pdf> -o <output.pdf> [options]
pii-strip <folder> [options]
```

A summary line is printed on stderr after each run.

### A folder of PDFs

Pass a folder instead of a file to redact every PDF directly in it (`.pdf` in any case), in name order. Each `<folder>/<name>.pdf` is written to `<folder>/processed/<name>-stripped.pdf`; the `processed` folder is created if needed.

- Subfolders and files that aren't PDFs are skipped and listed in a warning. Hidden files such as `.DS_Store` are skipped silently.
- `-o` can't be used with a folder. An existing file in `processed/` is only overwritten with `--force`.
- A file that fails (e.g. corrupt or encrypted) doesn't stop the run; the other files are still processed.
- Each file's summary line and messages start with its file name. A last line counts the files per result.
- The exit code is the most serious result over all files: `2`, then `1`, then `3`, then `0`.
- Every other option applies to each file. Names found in one file are not looked for in the others.
- With `--report`, one JSON file is written for the whole run (`schema_version` `2`), with one entry per PDF in `files`. A file that failed has its `error`. The report may be written inside `processed/`.

| Flag | What it does |
|---|---|
| `-o`, `--output PATH` | Where to write the redacted PDF. Required for a single PDF, not allowed with a folder. It can't be the input file. |
| `--force` | Overwrite the output file(s) if they already exist. |
| `--lang da,en` | Languages to analyze with, comma-separated. Default: `da,en` (every page is analyzed in both). |
| `--entities LIST` | Entity types to detect, comma-separated. Default: `PERSON,EMAIL_ADDRESS,DK_CPR,DK_PHONE,SOCIAL_PROFILE`. Supported: `PERSON`, `LOCATION`, `EMAIL_ADDRESS`, `DK_CPR`, `DK_PHONE`, `SOCIAL_PROFILE`. `SOCIAL_PROFILE` is a profile URL on LinkedIn (`linkedin.com/in/…`), Facebook, Instagram, X/Twitter, GitHub or TikTok; the whole URL is redacted. |
| `--deny FILE` | A text file with one term per line that is always redacted. |
| `--allow FILE` | A text file with one term per line that is never redacted. A term in both lists is redacted. |
| `--threshold 0.5` | Minimum score, from 0 to 1, for a finding to be redacted. Default: `0.5`. |
| `--keep-outline` | Keep the bookmarks. They are removed by default, because their titles can contain names. |
| `--allow-image-pages` | Accept pages that are only an image (e.g. scanned). They still can't be checked or redacted and are still listed in a warning, but the exit code is not `3`. |
| `--report FILE` | Write a JSON report of the run. It lists the findings with a hash of the matched text, not the text itself. |
| `--report-include-text` | Also write the matched text into the report. The report then contains personal data and must not be shared. Needs `--report`. |
| `--quiet` | Don't print the summary line. Warnings and errors are still printed. |
| `--version` | Print the version. |
| `-h`, `--help` | Print the help. |

Examples:

```bash
# Default: names, emails, CPR and phone numbers, social profile URLs, Danish and English
pii-strip interview.pdf -o interview-redacted.pdf

# English only, overwrite an existing output
pii-strip notes.pdf -o notes-redacted.pdf --lang en --force

# Also redact places, plus a project code name; never redact the company name
pii-strip case.pdf -o case-redacted.pdf --entities PERSON,LOCATION,EMAIL_ADDRESS,DK_CPR,DK_PHONE,SOCIAL_PROFILE --deny deny.txt --allow allow.txt

# Redact more aggressively
pii-strip case.pdf -o case-redacted.pdf --threshold 0.3

# Keep bookmarks and accept scanned pages
pii-strip report.pdf -o report-redacted.pdf --keep-outline --allow-image-pages

# Redact every PDF in a folder into cases/processed/, replacing earlier results
pii-strip cases/ --force

# Write a JSON report (hashes only), without the summary line
pii-strip case.pdf -o case-redacted.pdf --report run.json --quiet

# Write a report with the matched text, for your own review only
pii-strip case.pdf -o case-redacted.pdf --report run.json --report-include-text
```

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| `0` | The output was written and the verification pass found no personal data left in it. | Review the output anyway before you share it. |
| `1` | Error (for a folder: in at least one file, and no file has personal data left): wrong arguments, a folder without PDFs, a missing, encrypted or corrupt input file, an output that exists without `--force`, a missing model, or a report that couldn't be written. Nothing usable was produced. | Read the error message, fix the cause and run again. |
| `2` | The output was written, but personal data is **still in it**. The file is kept so you can inspect it. | **Do not share the output.** Check the listed entity types and pages, add the missed terms to a `--deny` file, and run again. |
| `3` | The output was written, but some pages are only images (e.g. scanned), so they were not checked or redacted. | Check the listed pages by hand. If they are safe, run again with `--allow-image-pages`. |

## Known limitations

- **Scanned pages.** Pages that are only an image are not OCR'd, checked or redacted. They are reported (exit code `3`).
- **Strings split across lines.** A name, email or number broken over two lines may be missed.
- **Danish addresses.** Street addresses (e.g. "Emil Holms Kanal 20, 2300 København S") are not detected. `LOCATION` catches cities and places, not addresses.
- **Names the NER model misses.** Unusual names, names in all caps and names in tables may be missed. Common words at the start of a sentence are sometimes redacted as names. Use `--deny` and `--allow` to correct this.
- **Names are redacted everywhere in the document.** Once a name is found on any page, the full name, the first name and the surname are redacted on every page, e.g. a surname alone in a footer. This knowingly over-redacts: a common surname such as `Hansen` is blacked out also where it belongs to someone else. Put such a word in the `--allow` file to keep it. A name part is only redacted in the same case or in capitals, so a surname that is also an ordinary word (`Skov`) is not removed in lowercase text (`skov`). Initials and inflected forms (`Jensens`) are not matched. Salutations and common job titles (`Kære`, `Dear`, `Head`, `Chief`, `Direktør` …) are cut off a name, so `Ryan Mendez Head of Innovation` only redacts `Ryan Mendez`; a title not on that list may still be redacted with the name.
- **Text in images, vector drawings or unusual font encodings** is not seen.

## Test data

Use **synthetic PDFs only**, e.g. generated with Faker as the tests do. Never commit real documents or real personal data to this repo, not even in an issue or a test fixture.

Run the tests with:

```bash
pip install -e ".[dev]"
pytest
```

## Offline guarantee

Documents with personal data must not leave your machine. Two things make sure of that:

- **An automated test** (`tests/test_offline.py`) blocks every network socket and runs the full pipeline (every entity type, deny and allow lists, sanitizing, the verification pass and the report). Any connection attempt fails the test, even if a library catches the error.
- **A manual check.** After installation, turn off Wi-Fi (and unplug the network cable), then run:

  ```bash
  pii-strip some-synthetic.pdf -o out.pdf --force
  echo $?
  ```

  It should finish with exit code `0` (or `2`/`3` for the reasons above), never with a network error.

## Licensing

- **PyMuPDF is licensed under AGPL-3.0.** That can affect how `pii-strip` may be distributed, and running it as a network service can trigger the AGPL's source-sharing obligations. **Check with DR Jura before you distribute the tool outside DR or run it as a service.** A commercial PyMuPDF license from Artifex is an alternative.
- Presidio (MIT) and spaCy (MIT) are permissively licensed.
- The models: `en_core_web_md` is MIT; `da_core_news_md` is CC BY-SA 4.0.
