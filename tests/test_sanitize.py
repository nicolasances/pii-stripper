import pymupdf

from pii_strip.redactor import redact_pdf
from pii_strip.sanitize import SanitizeCounts
from tests.support.pdf_factory import HIDDEN_PII, extract_text, make_hidden_pii_pdf, make_pdf, raw_bytes_contain


def test_fixture_holds_the_pii_in_the_raw_bytes_before_redaction(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")

    for name in ("author", "xmp", "comment", "attachment"):
        assert raw_bytes_contain(source, HIDDEN_PII[name]), name


def test_metadata_is_cleared(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    doc = pymupdf.open(output)
    assert not any(doc.metadata.get(field) for field in ("author", "title", "subject", "keywords", "creator", "producer", "creationDate", "modDate"))
    doc.close()


def test_xmp_metadata_is_removed(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    doc = pymupdf.open(output)
    assert HIDDEN_PII["xmp"] not in doc.get_xml_metadata()
    doc.close()


def test_annotations_are_removed(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    doc = pymupdf.open(output)
    assert all(len(list(page.annots())) == 0 for page in doc)
    doc.close()


def test_form_fields_are_removed(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    doc = pymupdf.open(output)
    assert all(len(list(page.widgets())) == 0 for page in doc)
    doc.close()


def test_embedded_files_are_removed(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    doc = pymupdf.open(output)
    assert doc.embfile_count() == 0
    doc.close()


def test_none_of_the_hidden_pii_is_in_the_raw_bytes(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    for name in ("author", "xmp", "comment", "form_value", "attachment"):
        assert not raw_bytes_contain(output, HIDDEN_PII[name]), name


def test_none_of_the_hidden_pii_is_in_any_object_of_the_file(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    doc = pymupdf.open(output)
    objects = []

    for xref in range(1, doc.xref_length()):
        objects.append(doc.xref_object(xref, compressed=False))

        if doc.xref_is_stream(xref):
            objects.append(doc.xref_stream(xref).decode("latin-1"))

    doc.close()

    for name in ("author", "xmp", "comment", "form_value", "attachment"):
        assert not any(HIDDEN_PII[name] in text for text in objects), name


def test_visible_text_is_unchanged(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    plain = make_pdf(tmp_path / "plain.pdf", ["Quarterly report for the board"])
    assert extract_text(output) == extract_text(plain)


def test_the_output_is_not_an_incremental_update(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert output.read_bytes().count(b"%%EOF") == 1


def test_counts_each_sanitize_action(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"
    counts = SanitizeCounts()

    redact_pdf(source, output, counts=counts)

    assert counts.metadata_fields == 6
    assert counts.xmp == 1
    assert counts.annotations == 1
    assert counts.form_fields == 1
    assert counts.embedded_files == 1


def test_bookmarks_are_removed_by_default(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"
    counts = SanitizeCounts()

    redact_pdf(source, output, counts=counts)

    doc = pymupdf.open(output)
    assert doc.get_toc() == []
    doc.close()
    assert not raw_bytes_contain(output, HIDDEN_PII["bookmark"])
    assert counts.bookmarks == 1


def test_bookmarks_are_kept_with_keep_outline(tmp_path):
    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    output = tmp_path / "out.pdf"
    counts = SanitizeCounts()

    redact_pdf(source, output, keep_outline=True, counts=counts)

    doc = pymupdf.open(output)
    assert [entry[1] for entry in doc.get_toc()] == [HIDDEN_PII["bookmark"]]
    doc.close()
    assert counts.bookmarks == 0
