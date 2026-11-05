from pathlib import Path

import pymupdf

from pii_strip.detector import find_pii_strings

BLACK = (0, 0, 0)


class RedactionError(Exception):
    """A problem with the input or output that the user can fix. The message is safe to show."""


def _open_pdf(path: Path) -> pymupdf.Document:
    if not path.exists():
        raise RedactionError(f"input file not found: {path}")

    try:
        doc = pymupdf.open(path)
    except Exception as error:
        raise RedactionError(f"{path} is not a PDF, or it is corrupt ({error})") from error

    if not doc.is_pdf:
        doc.close()
        raise RedactionError(f"{path} is not a PDF")

    if doc.needs_pass:
        doc.close()
        raise RedactionError(f"{path} is encrypted or password-protected, which is not supported")

    return doc


def redact_pdf(input_path: Path, output_path: Path, languages: list[str] | None = None, entities: list[str] | None = None) -> int:
    """Write a copy of the input PDF with detected PII truly removed (not just covered). Returns the number of redacted areas."""
    doc = _open_pdf(input_path)
    redacted_areas = 0

    for page in doc:
        for pii in find_pii_strings(page.get_text(), languages, entities):
            for rect in page.search_for(pii):
                page.add_redact_annot(rect, fill=BLACK)
                redacted_areas += 1

        page.apply_redactions()

    try:
        doc.save(output_path, garbage=4, deflate=True)
    except Exception as error:
        raise RedactionError(f"cannot write the output file {output_path} ({error})") from error
    finally:
        doc.close()

    return redacted_areas
