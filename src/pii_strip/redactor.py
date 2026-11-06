from pathlib import Path

import pymupdf

from pii_strip.detector import find_pii_strings
from pii_strip.term_lists import DEFAULT_THRESHOLD

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


def _is_whole_word_match(words_text: str, pii: str) -> bool:
    """True if the PII occurs in the words as whole words, or the words are a whole-word part of a PII that wraps over lines.
    'An' is not a match inside 'Anbefalinger' or 'transformation', but is one in 'An Nguyen' and in "Mette's".
    The case must be the same as the detected string, or all capitals (a heading): a capitalised false positive such as 'With' must not redact every 'with'."""
    if words_text.strip() and words_text in pii:
        return True

    for candidate in {pii, pii.upper()}:
        start = words_text.find(candidate)

        while start != -1:
            end = start + len(candidate)

            if (start == 0 or not words_text[start - 1].isalnum()) and (end == len(words_text) or not words_text[end].isalnum()):
                return True

            start = words_text.find(candidate, start + 1)

    return False


def _whole_word_hits(page: pymupdf.Page, pii: str, words: list) -> list[pymupdf.Rect]:
    """Where the PII occurs on the page. A plain text search also finds it inside longer words, which must not be redacted."""
    hits = []

    for rect in page.search_for(pii):
        area = pymupdf.Rect(rect.x0 + 0.5, rect.y0 + 0.5, rect.x1 - 0.5, rect.y1 - 0.5)
        words_text = " ".join(word[4] for word in words if pymupdf.Rect(word[:4]).intersects(area))

        if _is_whole_word_match(words_text, pii):
            hits.append(rect)

    return hits


def redact_pdf(input_path: Path, output_path: Path, languages: list[str] | None = None, entities: list[str] | None = None, threshold: float = DEFAULT_THRESHOLD, allow_terms: list[str] | None = None, deny_terms: list[str] | None = None) -> int:
    """Write a copy of the input PDF with detected PII truly removed (not just covered). Returns the number of redacted areas."""
    doc = _open_pdf(input_path)
    redacted_areas = 0

    for page in doc:
        words = page.get_text("words")

        for pii in find_pii_strings(page.get_text(), languages, entities, threshold, allow_terms, deny_terms):
            for rect in _whole_word_hits(page, pii, words):
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
