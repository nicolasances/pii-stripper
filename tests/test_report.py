from pii_strip.redactor import Finding
from pii_strip.report import summary_line
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
