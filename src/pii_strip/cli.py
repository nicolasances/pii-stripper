import argparse
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pii_strip import __version__
from pii_strip.nlp import DEFAULT_ENTITIES, ModelMissingError, SUPPORTED_ENTITIES, parse_entities, parse_languages, require_models, NER_ENTITIES
from pii_strip.pseudonymize import KEYS_FOLDER, PROCESSED_FOLDER, UNKNOWN_CANDIDATE, OutputFolderError, candidate_name, reset_output_folders, write_key
from pii_strip.redactor import Finding, RedactedString, RedactionError, redact_pdf
from pii_strip.report import build_file_entry, build_folder_report, build_report, summary_line, write_report
from pii_strip.sanitize import SanitizeCounts
from pii_strip.term_lists import DEFAULT_THRESHOLD, parse_threshold, read_term_list
from pii_strip.verify import verify_pdf

# The most serious result first: PII left in an output must never be hidden by another result
_SEVERITY = [2, 1, 3, 0]

DISCLAIMER = "This tool is assistive, not a guarantee: no detector finds all personal data. Always review the output before you share it."


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        """Raise instead of exiting with code 2, because exit code 2 is reserved for 'PII found after redaction'."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: error: {message}")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="pii-strip", description="Remove personally identifiable information from a PDF. The text is removed from the file, and a black box is drawn in its place.", epilog=DISCLAIMER)
    parser.add_argument("input", type=Path, help="the PDF to redact, or a folder: every PDF in it is redacted into <folder>/processed/<uuid>.pdf, with a key file per PDF in <folder>/keys/ (both folders are replaced on every run)")
    parser.add_argument("-o", "--output", type=Path, help="where to write the redacted PDF; required for a single PDF, not allowed with a folder")
    parser.add_argument("--force", action="store_true", help="overwrite the output file if it already exists (no effect with a folder, whose output folders are always replaced)")
    parser.add_argument("--lang", help="languages to analyze with, comma-separated (default: da,en)")
    parser.add_argument("--entities", help=f"entity types to detect, comma-separated (default: {','.join(DEFAULT_ENTITIES)}; supported: {','.join(SUPPORTED_ENTITIES)})")
    parser.add_argument("--deny", type=Path, help="a text file with one term per line that is always redacted")
    parser.add_argument("--allow", type=Path, help="a text file with one term per line that is never redacted (a term in both lists is redacted)")
    parser.add_argument("--threshold", help=f"minimum score, from 0 to 1, for a finding to be redacted (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--keep-outline", action="store_true", help="keep the bookmarks (outline); they are removed by default because their titles can contain names")
    parser.add_argument("--allow-image-pages", action="store_true", help="accept pages that are only an image (e.g. scanned): they can't be checked or redacted; they are still listed in a warning, but the exit code is not 3")
    parser.add_argument("--report", type=Path, help="write a JSON report of the run to this file; it lists the findings with a hash of the matched text, not the text itself")
    parser.add_argument("--report-include-text", action="store_true", help="also write the matched text into the report; the report then contains personal data and must not be shared")
    parser.add_argument("--quiet", action="store_true", help="don't print the summary line; warnings and errors are still printed")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser


def _same_file(first: Path, second: Path) -> bool:
    if first.exists() and second.exists():
        return first.samefile(second)

    return first.resolve() == second.resolve()


def _exit_code(residuals: list, image_only_pages: list[int], allow_image_pages: bool) -> int:
    """2 if PII is left in the output, else 3 if there are image-only pages that weren't accepted, else 0."""
    if residuals:
        return 2

    return 3 if image_only_pages and not allow_image_pages else 0


def _configuration(args: argparse.Namespace, languages: list[str], entities: list[str], threshold: float) -> dict:
    """The effective configuration for the report. The deny and allow lists are named by path, never by their contents."""
    return {
        "languages": languages,
        "entities": entities,
        "threshold": threshold,
        "deny_file": str(args.deny) if args.deny else None,
        "allow_file": str(args.allow) if args.allow else None,
        "keep_outline": args.keep_outline,
        "allow_image_pages": args.allow_image_pages,
        "report_include_text": args.report_include_text,
    }


@dataclass(frozen=True)
class Options:
    """The detection options that apply to every file of a run."""

    languages: list[str]
    entities: list[str]
    threshold: float
    deny_terms: list[str]
    allow_terms: list[str]


@dataclass
class FileRun:
    """The outcome of redacting one file: the exit code for that file and what the report needs. `error` is set if the file failed (exit code 1)."""

    input: Path
    output: Path
    started_at: datetime
    file_id: str | None = None
    exit_code: int = 0
    error: str | None = None
    findings: list[Finding] = field(default_factory=list)
    image_only_pages: list[int] = field(default_factory=list)
    counts: SanitizeCounts = field(default_factory=SanitizeCounts)
    residuals: list = field(default_factory=list)


def _error(message: str) -> int:
    print(f"pii-strip: error: {message}", file=sys.stderr)

    return 1


def _options(args: argparse.Namespace) -> Options:
    """Read and check the detection options. Raises ValueError or ModelMissingError with a message for the user."""
    languages = parse_languages(args.lang)
    entities = parse_entities(args.entities)
    threshold = parse_threshold(args.threshold)
    deny_terms = read_term_list(args.deny) if args.deny else []
    allow_terms = read_term_list(args.allow) if args.allow else []

    if any(entity in NER_ENTITIES for entity in entities):
        require_models(languages)

    return Options(languages, entities, threshold, deny_terms, allow_terms)


def _redact_file(args: argparse.Namespace, options: Options, input_path: Path, output_path: Path, label: str = "") -> FileRun:
    """Redact, verify and print the messages for one file. Every message names the file with `label` (e.g. 'a.pdf: '), which is empty for a single-file run."""
    run = FileRun(input_path, output_path, datetime.now(timezone.utc))
    redacted: list[RedactedString] = []

    try:
        redact_pdf(input_path, output_path, options.languages, options.entities, options.threshold, options.allow_terms, options.deny_terms, args.keep_outline, counts=run.counts, redacted=redacted, image_only_pages=run.image_only_pages, findings=run.findings)
    except RedactionError as error:
        run.exit_code, run.error = _error(f"{label}{error}"), str(error)

        return run

    if run.image_only_pages:
        pages = ", ".join(str(number) for number in run.image_only_pages)
        print(f"pii-strip: warning: {label}image-only page(s) found, e.g. scanned pages. They were not checked or redacted and may contain personal data: page {pages}", file=sys.stderr)

    run.residuals = verify_pdf(output_path, redacted, options.languages, options.entities, options.threshold, options.allow_terms, options.deny_terms)

    if not args.quiet:
        print(f"{label}{summary_line(run.findings, run.counts, run.residuals)}", file=sys.stderr)

    if run.residuals:
        print(f"pii-strip: error: {label}the output is not clean: personal data is still in {output_path}. The file was kept so you can inspect it. Do not share it.", file=sys.stderr)

        for residual in run.residuals:
            print(f"  {residual.entity_type} on page {residual.page}", file=sys.stderr)

    run.exit_code = _exit_code(run.residuals, run.image_only_pages, args.allow_image_pages)

    return run


def _most_serious(exit_codes: list[int]) -> int:
    return min(exit_codes, key=_SEVERITY.index, default=0)


def _folder_inputs(folder: Path) -> tuple[list[Path], list[Path]]:
    """The PDFs directly in the folder, in name order, and the entries that are skipped: subfolders and other files. Hidden entries and the output folders are left out of both."""
    entries = sorted(entry for entry in folder.iterdir() if not entry.name.startswith(".") and entry.name not in (PROCESSED_FOLDER, KEYS_FOLDER))
    pdfs = [entry for entry in entries if entry.is_file() and entry.suffix.lower() == ".pdf"]

    return pdfs, [entry for entry in entries if entry not in pdfs]


def _folder_summary(runs: list[FileRun]) -> str:
    """One line for the whole folder run, e.g. 'processed 3 files: 1 clean, 1 with personal data left (2), 1 failed (1)'."""
    labels = {0: "clean", 2: "with personal data left (2)", 1: "failed (1)", 3: "with image-only pages (3)"}
    parts = [f"{count} {labels[code]}" for code in [0, 2, 1, 3] if (count := sum(run.exit_code == code for run in runs))]
    files = "file" if len(runs) == 1 else "files"

    return f"processed {len(runs)} {files}: {', '.join(parts)}"


def _write_report(args: argparse.Namespace, report: dict, exit_code: int) -> int:
    """Write the report and return the final exit code: 1 if the report can't be written, unless PII is left in an output (2)."""
    try:
        write_report(args.report, report)
    except OSError as error:
        _error(f"cannot write the report {args.report} ({error})")

        return 2 if exit_code == 2 else 1

    if args.report_include_text:
        print(f"pii-strip: warning: the report {args.report} contains personal data (the matched text). Do not share it.", file=sys.stderr)

    return exit_code


def _without_original_name(text: str | None, run: FileRun) -> str | None:
    """The text with the input path and file name replaced by the file's UUID, so the report can't give the original name (and with it the person) away."""
    if text is None:
        return None

    return text.replace(str(run.input), run.file_id).replace(run.input.name, run.file_id)


def _main_folder(args: argparse.Namespace, options: Options) -> int:
    folder = args.input
    started_at = datetime.now(timezone.utc)
    pdfs, skipped = _folder_inputs(folder)
    processed = folder / PROCESSED_FOLDER

    if not pdfs:
        return _error(f"no PDF files found in the folder {folder}")

    if args.report and any(_same_file(args.report, path) for path in pdfs):
        return _error("the report can't be written to an input file; choose a different report path")

    if skipped:
        print(f"pii-strip: warning: skipped (not a PDF, or a folder): {', '.join(entry.name for entry in skipped)}", file=sys.stderr)

    try:
        deleted = reset_output_folders(folder)
    except OutputFolderError as error:
        return _error(str(error))

    if deleted:
        print(f"pii-strip: warning: deleted the earlier results in {', '.join(f'{path}/' for path in deleted)}", file=sys.stderr)

    runs = []

    for pdf in pdfs:
        file_id = str(uuid.uuid4())
        run = _redact_file(args, options, pdf, processed / f"{file_id}.pdf", f"{pdf.name}: ")
        run.file_id = file_id
        candidate = candidate_name(run.findings)

        if candidate is None and run.error is None:
            print(f"pii-strip: warning: {pdf.name}: no candidate name found (no full name of at least two words); the key file says '{UNKNOWN_CANDIDATE}'", file=sys.stderr)

        try:
            write_key(folder, file_id, candidate or UNKNOWN_CANDIDATE, pdf.name, run.output, run.started_at, run.exit_code)
        except OSError as error:
            run.exit_code = _most_serious([run.exit_code, _error(f"{pdf.name}: cannot write the key file ({error})")])

        runs.append(run)

    exit_code = _most_serious([run.exit_code for run in runs])

    if not args.quiet or exit_code != 0:
        print(_folder_summary(runs), file=sys.stderr)

    if not args.report:
        return exit_code

    configuration = _configuration(args, options.languages, options.entities, options.threshold)
    files = [build_file_entry(run.file_id, run.output, run.started_at, run.findings, run.image_only_pages, run.counts, run.residuals, run.exit_code, _without_original_name(run.error, run), args.report_include_text) for run in runs]

    return _write_report(args, build_folder_report(folder, processed, started_at, configuration, files, exit_code), exit_code)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except UsageError as error:
        print(error, file=sys.stderr)

        return 1

    is_folder = args.input.is_dir()

    if is_folder and args.output:
        return _error("-o/--output can't be used with a folder; the redacted files are written to <folder>/processed/")

    if not is_folder and not args.output:
        return _error("the -o/--output argument is required for a single PDF")

    if args.report_include_text and not args.report:
        return _error("--report-include-text needs --report")

    if not is_folder:
        if _same_file(args.input, args.output):
            return _error("the input and output are the same file; choose a different output path")

        if args.report and (_same_file(args.report, args.input) or _same_file(args.report, args.output)):
            return _error("the report can't be written to the input or output file; choose a different report path")

        if args.output.exists() and not args.force:
            return _error(f"{args.output} already exists; use --force to overwrite it")

    try:
        options = _options(args)
    except (ValueError, ModelMissingError) as error:
        return _error(str(error))

    if is_folder:
        return _main_folder(args, options)

    run = _redact_file(args, options, args.input, args.output)

    if run.error is not None or not args.report:
        return run.exit_code

    configuration = _configuration(args, options.languages, options.entities, options.threshold)
    report = build_report(args.input, args.output, run.started_at, configuration, run.findings, run.image_only_pages, run.counts, run.residuals, run.exit_code, args.report_include_text)

    return _write_report(args, report, run.exit_code)


if __name__ == "__main__":
    sys.exit(main())
