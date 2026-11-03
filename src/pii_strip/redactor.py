from pathlib import Path

import pymupdf

from pii_strip.detector import find_pii_strings

BLACK = (0, 0, 0)


def redact_pdf(input_path: Path, output_path: Path) -> int:
    """Write a copy of the input PDF with detected PII truly removed (not just covered). Returns the number of redacted areas."""
    doc = pymupdf.open(input_path)
    redacted_areas = 0

    for page in doc:
        for pii in find_pii_strings(page.get_text()):
            for rect in page.search_for(pii):
                page.add_redact_annot(rect, fill=BLACK)
                redacted_areas += 1

        page.apply_redactions()

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

    return redacted_areas
