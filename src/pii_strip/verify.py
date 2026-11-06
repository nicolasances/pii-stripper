import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from pii_strip.detector import find_pii_results
from pii_strip.redactor import RedactedString
from pii_strip.term_lists import DEFAULT_THRESHOLD


@dataclass(frozen=True)
class Residual:
    """PII left in the output. Only the entity type and the page (from 1) are kept, so reporting it can't leak the text."""

    entity_type: str
    page: int


def _contains_whole_word(text: str, pii: str) -> bool:
    """Case-insensitive and whole-word, like the redaction. Whitespace inside the string also matches a line break."""
    if not pii.strip():
        return False

    pattern = r"\s+".join(re.escape(word) for word in pii.split())

    return re.search(rf"(?<!\w){pattern}(?!\w)", text, flags=re.IGNORECASE) is not None


def verify_pdf(path: Path, redacted: list[RedactedString], languages: list[str] | None = None, entities: list[str] | None = None, threshold: float = DEFAULT_THRESHOLD, allow_terms: list[str] | None = None, deny_terms: list[str] | None = None) -> list[Residual]:
    """Reopen the saved output from disk and return what is left: any redacted string that can still be found, and anything detection finds again with the same configuration.
    Each entity type is reported once per page, ordered by page."""
    residuals = set()
    doc = pymupdf.open(path)

    try:
        for number, page in enumerate(doc, start=1):
            text = page.get_text()
            residuals.update(Residual(item.entity_type, number) for item in redacted if _contains_whole_word(text, item.text))
            residuals.update(Residual(result.entity_type, number) for result in find_pii_results(text, languages, entities, threshold, allow_terms, deny_terms))
    finally:
        doc.close()

    return sorted(residuals, key=lambda residual: (residual.page, residual.entity_type))
