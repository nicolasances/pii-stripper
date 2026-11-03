import argparse
import sys
from pathlib import Path

from pii_strip.redactor import redact_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pii-strip", description="Remove personally identifiable information from a PDF.")
    parser.add_argument("input", type=Path, help="the PDF to redact")
    parser.add_argument("-o", "--output", type=Path, required=True, help="where to write the redacted PDF")
    args = parser.parse_args(argv)

    redacted_areas = redact_pdf(args.input, args.output)

    print(f"redacted {redacted_areas} item(s)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
