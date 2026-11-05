import argparse
import sys
from pathlib import Path

from pii_strip import __version__
from pii_strip.nlp import ModelMissingError, SUPPORTED_ENTITIES, parse_entities, parse_languages, require_models, NER_ENTITIES
from pii_strip.redactor import RedactionError, redact_pdf

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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser


def _same_file(first: Path, second: Path) -> bool:
    if first.exists() and second.exists():
        return first.samefile(second)

    return first.resolve() == second.resolve()


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except UsageError as error:
        print(error, file=sys.stderr)

        return 1

    if _same_file(args.input, args.output):
        print("pii-strip: error: the input and output are the same file; choose a different output path", file=sys.stderr)

        return 1

    if args.output.exists() and not args.force:
        print(f"pii-strip: error: {args.output} already exists; use --force to overwrite it", file=sys.stderr)

        return 1

    try:
        languages = parse_languages(args.lang)
        entities = parse_entities(args.entities)

        if any(entity in NER_ENTITIES for entity in entities):
            require_models(languages)
    except (ValueError, ModelMissingError) as error:
        print(f"pii-strip: error: {error}", file=sys.stderr)

        return 1

    try:
        redacted_areas = redact_pdf(args.input, args.output, languages, entities)
    except RedactionError as error:
        print(f"pii-strip: error: {error}", file=sys.stderr)

        return 1

    print(f"redacted {redacted_areas} item(s)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
