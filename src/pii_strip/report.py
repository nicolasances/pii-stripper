import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from pii_strip import __version__
from pii_strip.cpr import DK_CPR
from pii_strip.redactor import Finding
from pii_strip.sanitize import SanitizeCounts
from pii_strip.verify import Residual

REPORT_SCHEMA_VERSION = 1


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


def _hash(finding: Finding) -> str | None:
    """SHA-256 of the matched text, so a developer can check whether a value was redacted without the report revealing it.
    CPR numbers get no hash: there are few enough of them that the hash can be reversed by trying them all."""
    if finding.entity_type == DK_CPR:
        return None

    return hashlib.sha256(finding.text.encode("utf-8")).hexdigest()


def _finding_entry(finding: Finding) -> dict:
    return {
        "entity_type": finding.entity_type,
        "page": finding.page,
        "score": finding.score,
        "language": finding.language,
        "source": finding.source,
        "areas": [list(area) for area in finding.areas],
        "sha256": _hash(finding),
    }


def build_report(input_path: Path, output_path: Path, started_at: datetime, configuration: dict, findings: list[Finding], image_only_pages: list[int], counts: SanitizeCounts, residuals: list[Residual], exit_code: int) -> dict:
    """The JSON report of a run (F09). It holds no matched text, only a hash of it; residuals are listed by entity type and page only."""
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "pii-strip", "version": __version__},
        "run": {"input": str(input_path), "output": str(output_path), "started_at": started_at.isoformat()},
        "configuration": configuration,
        "findings": [_finding_entry(finding) for finding in findings],
        "image_only_pages": image_only_pages,
        "sanitize": asdict(counts),
        "verification": {"status": "failed" if residuals else "ok", "residuals": [asdict(residual) for residual in residuals]},
        "exit_code": exit_code,
    }


def write_report(path: Path, report: dict) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
