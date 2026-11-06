from collections import Counter

from pii_strip.redactor import Finding
from pii_strip.sanitize import SanitizeCounts
from pii_strip.verify import Residual


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _redacted_part(findings: list[Finding]) -> str:
    per_entity = Counter()

    for finding in findings:
        per_entity[finding.entity_type] += len(finding.areas)

    items = sum(per_entity.values())

    if not items:
        return "redacted 0 items"

    pages = len({finding.page for finding in findings if finding.areas})
    entities = ", ".join(f"{entity} {count}" for entity, count in sorted(per_entity.items()) if count)

    return f"redacted {_plural(items, 'item')} on {_plural(pages, 'page')} ({entities})"


def _sanitized_part(counts: SanitizeCounts) -> str:
    actions = [
        "metadata" if counts.metadata_fields else "",
        "XMP" if counts.xmp else "",
        _plural(counts.annotations, "annotation") if counts.annotations else "",
        _plural(counts.form_fields, "form field") if counts.form_fields else "",
        _plural(counts.embedded_files, "embedded file") if counts.embedded_files else "",
        _plural(counts.bookmarks, "bookmark") if counts.bookmarks else "",
    ]

    return f"sanitized: {', '.join(action for action in actions if action) or 'nothing'}"


def summary_line(findings: list[Finding], counts: SanitizeCounts, residuals: list[Residual]) -> str:
    """One line about the run: what was redacted (areas per entity type, and on how many pages), what hidden content was removed, and the verification status. It holds no matched text."""
    verification = f"verification FAILED ({len(residuals)} left)" if residuals else "verification OK"

    return f"{_redacted_part(findings)}; {_sanitized_part(counts)}; {verification}"
