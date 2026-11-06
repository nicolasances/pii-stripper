import hashlib
from datetime import datetime, timezone
from pathlib import Path

from pii_strip import __version__
from pii_strip.redactor import Finding
from pii_strip.report import REPORT_SCHEMA_VERSION, build_report, summary_line
from pii_strip.sanitize import SanitizeCounts
from pii_strip.verify import Residual


def _finding(entity_type: str, page: int, areas: int) -> Finding:
    return Finding(text="synthetic", entity_type=entity_type, page=page, score=0.9, language=None, source="pattern", areas=tuple((0.0, 0.0, 1.0, 1.0) for _ in range(areas)))


def test_the_summary_counts_redacted_areas_per_entity_type_and_pages():
    findings = [_finding("PERSON", 1, 2), _finding("EMAIL_ADDRESS", 3, 1), _finding("PERSON", 3, 1)]

    line = summary_line(findings, SanitizeCounts(), [])

    assert line.startswith("redacted 4 items on 2 pages (EMAIL_ADDRESS 1, PERSON 3)")


def test_the_summary_uses_the_singular_for_one_item_on_one_page():
    line = summary_line([_finding("DK_CPR", 1, 1)], SanitizeCounts(), [])

    assert line.startswith("redacted 1 item on 1 page (DK_CPR 1)")


def test_a_finding_without_areas_is_not_counted():
    line = summary_line([_finding("PERSON", 1, 0)], SanitizeCounts(), [])

    assert line.startswith("redacted 0 items;")


def test_the_summary_lists_the_sanitize_actions():
    counts = SanitizeCounts(metadata_fields=3, xmp=1, annotations=4, form_fields=1, embedded_files=2, bookmarks=5)

    line = summary_line([], counts, [])

    assert "sanitized: metadata, XMP, 4 annotations, 1 form field, 2 embedded files, 5 bookmarks" in line


def test_the_summary_says_when_nothing_was_sanitized():
    assert "sanitized: nothing" in summary_line([], SanitizeCounts(), [])


def test_the_summary_says_verification_ok_when_nothing_is_left():
    assert summary_line([], SanitizeCounts(), []).endswith("verification OK")


def test_the_summary_says_verification_failed_with_the_number_of_residuals():
    residuals = [Residual("PERSON", 1), Residual("EMAIL_ADDRESS", 2)]

    assert summary_line([], SanitizeCounts(), residuals).endswith("verification FAILED (2 left)")


def _report(findings: list[Finding]) -> dict:
    return build_report(Path("in.pdf"), Path("out.pdf"), datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc), {"languages": ["da"]}, findings, [3], SanitizeCounts(annotations=2), [Residual("PERSON", 1)], 2)


def test_the_report_has_a_schema_version_and_every_section():
    report = _report([_finding("PERSON", 1, 1)])

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["tool"] == {"name": "pii-strip", "version": __version__}
    assert report["run"] == {"input": "in.pdf", "output": "out.pdf", "started_at": "2026-01-02T03:04:05+00:00"}
    assert report["configuration"] == {"languages": ["da"]}
    assert report["image_only_pages"] == [3]
    assert report["sanitize"]["annotations"] == 2
    assert report["verification"] == {"status": "failed", "residuals": [{"entity_type": "PERSON", "page": 1}]}
    assert report["exit_code"] == 2


def test_a_finding_in_the_report_has_a_sha256_of_the_text_and_no_text():
    finding = Finding(text="mette@example.invalid", entity_type="EMAIL_ADDRESS", page=2, score=1.0, language=None, source="pattern", areas=((1.0, 2.0, 3.0, 4.0),))

    entry = _report([finding])["findings"][0]

    assert entry == {"entity_type": "EMAIL_ADDRESS", "page": 2, "score": 1.0, "language": None, "source": "pattern", "areas": [[1.0, 2.0, 3.0, 4.0]], "sha256": hashlib.sha256(b"mette@example.invalid").hexdigest()}


def test_a_cpr_finding_has_no_hash_because_a_cpr_hash_can_be_brute_forced():
    finding = Finding(text="010190-1234", entity_type="DK_CPR", page=1, score=1.0, language=None, source="pattern", areas=())

    assert _report([finding])["findings"][0]["sha256"] is None


def test_verification_is_ok_when_nothing_is_left():
    report = build_report(Path("in.pdf"), Path("out.pdf"), datetime.now(timezone.utc), {}, [], [], SanitizeCounts(), [], 0)

    assert report["verification"] == {"status": "ok", "residuals": []}
