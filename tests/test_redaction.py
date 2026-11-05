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


def test_redacts_cpr_numbers_in_all_three_formats_in_one_document(tmp_path):
    numbers = ["010190-1234", "150385 4321", "2711951234"]
    source = make_pdf(tmp_path / "in.pdf", [f"Dash {numbers[0]}", f"Space {numbers[1]}", f"CPR {numbers[2]}"])
    output = tmp_path / "out.pdf"

    count = redact_pdf(source, output)

    text = extract_text(output)
    assert all(number not in text for number in numbers)
    assert count == 3


def test_redacts_danish_phone_numbers_in_every_format_with_and_without_a_prefix(tmp_path):
    numbers = ["12345678", "12 34 56 78", "1234 5678", "12-34-56-78", "+45 12345678", "0045 12 34 56 78", "(+45) 1234 5678", "+4512-34-56-78"]
    source = make_pdf(tmp_path / "in.pdf", [f"Tlf. {number}" for number in numbers])
    output = tmp_path / "out.pdf"

    count = redact_pdf(source, output)

    text = extract_text(output)
    assert all(number not in text for number in numbers)
    assert count == len(numbers)


def test_keeps_a_date_and_an_amount_written_with_eight_digits(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Dato 01012024 og beløb 12.345.678 kr."])
    output = tmp_path / "out.pdf"

    count = redact_pdf(source, output)

    text = extract_text(output)
    assert "01012024" in text
    assert "12.345.678" in text
    assert count == 0


def test_a_short_detected_string_is_not_redacted_inside_longer_words(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor.find_pii_strings", lambda text, languages=None, entities=None: {"An"})
    source = make_pdf(tmp_path / "in.pdf", ["UDVALGTE Anbefalinger: An Nguyen led the transformation and the organization."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert "Anbefalinger" in text
    assert "transformation" in text
    assert "organization" in text


def test_a_short_detected_string_is_still_redacted_as_a_whole_word(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor.find_pii_strings", lambda text, languages=None, entities=None: {"An"})
    source = make_pdf(tmp_path / "in.pdf", ["Anbefalinger: An Nguyen led the work."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert "Nguyen led" in extract_text(output)
    assert "An Nguyen" not in extract_text(output)
    assert "Anbefalinger" in extract_text(output)


def test_a_name_followed_by_a_possessive_or_punctuation_is_still_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor.find_pii_strings", lambda text, languages=None, entities=None: {"Mette"})
    source = make_pdf(tmp_path / "in.pdf", ["Mette, Mette's bil og (Mette) kom."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert "Mette" not in extract_text(output)


def test_a_name_split_across_two_lines_is_still_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor.find_pii_strings", lambda text, languages=None, entities=None: {"Mette Hansen"})
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Kontakt Mette", fontsize=11)
    page.insert_text((72, 90), "Hansen i dag.", fontsize=11)
    source = tmp_path / "in.pdf"
    doc.save(source)
    doc.close()
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert "Mette" not in text
    assert "Hansen" not in text


def test_a_capitalised_detected_word_does_not_redact_the_same_word_in_lowercase(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor.find_pii_strings", lambda text, languages=None, entities=None: {"With"})
    source = make_pdf(tmp_path / "in.pdf", ["With care. He works with the team."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    text = extract_text(output)
    assert "works with the team" in text
    assert "With care" not in text


def test_a_name_written_in_capitals_is_still_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor.find_pii_strings", lambda text, languages=None, entities=None: {"Mette Hansen"})
    source = make_pdf(tmp_path / "in.pdf", ["Signed: METTE HANSEN, today."])
    output = tmp_path / "out.pdf"

    redact_pdf(source, output)

    assert "METTE" not in extract_text(output)
