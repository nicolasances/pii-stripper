import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from pii_strip import __version__
from pii_strip.nlp import ModelMissingError, SUPPORTED_ENTITIES, parse_entities, parse_languages, require_models, NER_ENTITIES
from pii_strip.redactor import Finding, RedactedString, RedactionError, redact_pdf
from pii_strip.report import build_report, summary_line, write_report
from pii_strip.sanitize import SanitizeCounts
from pii_strip.term_lists import DEFAULT_THRESHOLD, parse_threshold, read_term_list
from pii_strip.verify import verify_pdf

DISCLAIMER = "This tool is assistive, not a guarantee: no detector finds all personal data. Always review the output before you share it."


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        """Raise instead of exiting with code 2, because exit code 2 is reserved for 'PII found after redaction'."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: error: {message}")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="pii-strip", description="Remove personally identifiable information from a PDF. The text is removed from the file, and a black box is drawn in its place.", epilog=DISCLAIMER)
    parser.add_argument("input", type=Path, help="the PDF to redact")
    parser.add_argument("-o", "--output", type=Path, required=True, help="where to write the redacted PDF")
    parser.add_argument("--force", action="store_true", help="overwrite the output file if it already exists")
    parser.add_argument("--lang", help="languages to analyze with, comma-separated (default: da,en)")
    parser.add_argument("--entities", help=f"entity types to detect, comma-separated (default: PERSON,EMAIL_ADDRESS,DK_CPR,DK_PHONE; supported: {','.join(SUPPORTED_ENTITIES)})")
    parser.add_argument("--deny", type=Path, help="a text file with one term per line that is always redacted")
    parser.add_argument("--allow", type=Path, help="a text file with one term per line that is never redacted (a term in both lists is redacted)")
    parser.add_argument("--threshold", help=f"minimum score, from 0 to 1, for a finding to be redacted (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--keep-outline", action="store_true", help="keep the bookmarks (outline); they are removed by default because their titles can contain names")
    parser.add_argument("--allow-image-pages", action="store_true", help="accept pages that are only an image (e.g. scanned): they can't be checked or redacted; they are still listed in a warning, but the exit code is not 3")
    parser.add_argument("--report", type=Path, help="write a JSON report of the run to this file; it lists the findings with a hash of the matched text, not the text itself")
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
    }


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except UsageError as error:
        print(error, file=sys.stderr)

        return 1

    if _same_file(args.input, args.output):
        print("pii-strip: error: the input and output are the same file; choose a different output path", file=sys.stderr)

        return 1

    if args.report and (_same_file(args.report, args.input) or _same_file(args.report, args.output)):
        print("pii-strip: error: the report can't be written to the input or output file; choose a different report path", file=sys.stderr)

        return 1

    if args.output.exists() and not args.force:
        print(f"pii-strip: error: {args.output} already exists; use --force to overwrite it", file=sys.stderr)

        return 1

    try:
        languages = parse_languages(args.lang)
        entities = parse_entities(args.entities)
        threshold = parse_threshold(args.threshold)
        deny_terms = read_term_list(args.deny) if args.deny else []
        allow_terms = read_term_list(args.allow) if args.allow else []

        if any(entity in NER_ENTITIES for entity in entities):
            require_models(languages)
    except (ValueError, ModelMissingError) as error:
        print(f"pii-strip: error: {error}", file=sys.stderr)

        return 1

    started_at = datetime.now(timezone.utc)
    redacted: list[RedactedString] = []
    image_only_pages: list[int] = []
    findings: list[Finding] = []
    counts = SanitizeCounts()

    try:
        redact_pdf(args.input, args.output, languages, entities, threshold, allow_terms, deny_terms, args.keep_outline, counts=counts, redacted=redacted, image_only_pages=image_only_pages, findings=findings)
    except RedactionError as error:
        print(f"pii-strip: error: {error}", file=sys.stderr)

        return 1

    if image_only_pages:
        pages = ", ".join(str(number) for number in image_only_pages)
        print(f"pii-strip: warning: image-only page(s) found, e.g. scanned pages. They were not checked or redacted and may contain personal data: page {pages}", file=sys.stderr)

    residuals = verify_pdf(args.output, redacted, languages, entities, threshold, allow_terms, deny_terms)

    if not args.quiet:
        print(summary_line(findings, counts, residuals), file=sys.stderr)

    if residuals:
        print(f"pii-strip: error: the output is not clean: personal data is still in {args.output}. The file was kept so you can inspect it. Do not share it.", file=sys.stderr)

        for residual in residuals:
            print(f"  {residual.entity_type} on page {residual.page}", file=sys.stderr)

    exit_code = _exit_code(residuals, image_only_pages, args.allow_image_pages)

    if args.report:
        configuration = _configuration(args, languages, entities, threshold)
        report = build_report(args.input, args.output, started_at, configuration, findings, image_only_pages, counts, residuals, exit_code)

        try:
            write_report(args.report, report)
        except OSError as error:
            print(f"pii-strip: error: cannot write the report {args.report} ({error})", file=sys.stderr)

            return 2 if exit_code == 2 else 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
