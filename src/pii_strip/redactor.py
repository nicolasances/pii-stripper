from dataclasses import dataclass
from pathlib import Path

import pymupdf

from pii_strip.detector import find_distinct_pii_results, language_of, source_of
from pii_strip.sanitize import SanitizeCounts, sanitize
from pii_strip.term_lists import DEFAULT_THRESHOLD

BLACK = (0, 0, 0)


class RedactionError(Exception):
    """A problem with the input or output that the user can fix. The message is safe to show."""


@dataclass(frozen=True)
class RedactedString:
    """A string that was detected as PII and meant to be redacted. Passed to the verification (F07)."""

    text: str
    entity_type: str


@dataclass(frozen=True)
class Finding:
    """A string redacted on a page (from 1), how it was found, and the areas (x0, y0, x1, y1) blacked out for it. Passed to the summary and the report (F09)."""

    text: str
    entity_type: str
    page: int
    score: float
    language: str | None
    source: str
    areas: tuple[tuple[float, float, float, float], ...]


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


def _is_image_only(page: pymupdf.Page, text: str) -> bool:
    """No extractable text and at least one image, typically a scanned page. A blank page is not image-only."""
    return not text.strip() and len(page.get_images()) > 0


def redact_pdf(input_path: Path, output_path: Path, languages: list[str] | None = None, entities: list[str] | None = None, threshold: float = DEFAULT_THRESHOLD, allow_terms: list[str] | None = None, deny_terms: list[str] | None = None, keep_outline: bool = False, counts: SanitizeCounts | None = None, redacted: list[RedactedString] | None = None, image_only_pages: list[int] | None = None, findings: list[Finding] | None = None) -> int:
    """Write a copy of the input PDF with detected PII truly removed (not just covered). Returns the number of redacted areas.
    Hidden content (metadata, XMP, annotations, form fields, embedded files, and bookmarks unless keep_outline is set) is always removed; the counts of what was removed are written to `counts` if given.
    Every string detected as PII is appended to `redacted` if given, also when no area was found for it on the page.
    The number (from 1) of every page that has no text but an image, and so can't be checked, is appended to `image_only_pages` if given. Those pages are passed through unchanged.
    Every distinct string detected on a page is appended to `findings` if given, with its areas on that page (none if the redaction search misses it)."""
    doc = _open_pdf(input_path)
    redacted_areas = 0

    for number, page in enumerate(doc, start=1):
        text = page.get_text()
        words = page.get_text("words")

        if image_only_pages is not None and _is_image_only(page, text):
            image_only_pages.append(number)

        for pii, result in find_distinct_pii_results(text, languages, entities, threshold, allow_terms, deny_terms).items():
            if redacted is not None:
                redacted.append(RedactedString(pii, result.entity_type))

            rects = _whole_word_hits(page, pii, words)

            for rect in rects:
                page.add_redact_annot(rect, fill=BLACK)
                redacted_areas += 1

            if findings is not None:
                findings.append(Finding(pii, result.entity_type, number, result.score, language_of(result), source_of(result), tuple((rect.x0, rect.y0, rect.x1, rect.y1) for rect in rects)))

        page.apply_redactions()

    sanitize_counts = sanitize(doc, keep_outline)

    if counts is not None:
        counts.__dict__.update(sanitize_counts.__dict__)

    try:
        doc.save(output_path, garbage=4, deflate=True, incremental=False)
    except Exception as error:
        raise RedactionError(f"cannot write the output file {output_path} ({error})") from error
    finally:
        doc.close()

    return redacted_areas
