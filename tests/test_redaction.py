import pymupdf
import pytest
from faker import Faker

from pii_strip.redactor import redact_pdf
from tests.support.pdf_factory import extract_text, make_pdf, page_count

fake = Faker("da_DK")
Faker.seed(1234)


def test_removes_email_from_extracted_text(tmp_path):
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"Kontakt os på {email} for mere information."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert email not in extract_text(output)


def test_keeps_text_that_is_not_pii(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", [f"Hello world. Write to {fake.email()} soon."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert "Hello world." in text
    assert "soon." in text


def test_keeps_the_page_count(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", [f"Page one {fake.email()}", "Page two has nothing", f"Page three {fake.email()}"])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert page_count(output) == 3


def test_redacts_the_email_on_every_page(tmp_path):
    first = fake.email()
    second = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"One: {first}", f"Two: {second}"])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert first not in text
    assert second not in text


def test_redacts_every_occurrence_of_the_same_email_on_a_page(tmp_path):
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"From {email} to someone, cc {email}."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert email not in extract_text(output)


def test_leaves_the_input_file_unchanged(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", [f"Mail {fake.email()}"])
    before = source.read_bytes()

    redact_pdf(source, tmp_path / "out.pdf")

    assert source.read_bytes() == before


def test_returns_the_number_of_redacted_items(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", [f"{fake.email()} and {fake.email()}"])

    count = redact_pdf(source, tmp_path / "out.pdf")

    assert count == 2


def test_a_pdf_without_pii_is_copied_with_nothing_redacted(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Nothing personal here."])
    output = tmp_path / "out.pdf"

    count = redact_pdf(source, output)

    assert count == 0
    assert "Nothing personal here." in extract_text(output)


def test_draws_a_black_box_where_the_email_was(tmp_path):
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"Mail {email}"])
    output = tmp_path / "out.pdf"
    original = pymupdf.open(source)
    area = original[0].search_for(email)[0]
    original.close()

    redact_pdf(source, output)

    redacted = pymupdf.open(output)
    pixmap = redacted[0].get_pixmap(clip=area)
    redacted.close()
    centre = pixmap.pixel(pixmap.width // 2, pixmap.height // 2)
    assert centre[:3] == (0, 0, 0)


@pytest.mark.xfail(strict=True, reason="Known limitation (F01 OQ-02): an email wrapped across two lines is not detected, so it is not redacted")
def test_redacts_an_email_that_is_split_across_two_lines(tmp_path):
    source = tmp_path / "in.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Write to anna.jensen@", fontsize=11)
    page.insert_text((72, 90), "example.dk today", fontsize=11)
    doc.save(source)
    doc.close()
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert "anna.jensen@" not in text


@pytest.mark.parametrize("cpr", ["010190-1234", "150385 4321"])
def test_removes_a_delimited_cpr_number_from_extracted_text(tmp_path, cpr):
    source = make_pdf(tmp_path / "in.pdf", [f"CPR-nr: {cpr} for borgeren."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert cpr not in text
    assert "for borgeren." in text
