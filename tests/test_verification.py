from faker import Faker

from pii_strip.redactor import RedactedString
from pii_strip.verify import Residual, verify_pdf
from tests.support.pdf_factory import make_pdf

fake = Faker("da_DK")
Faker.seed(707)


def test_a_clean_output_has_no_residuals(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["Quarterly report for the board"])

    residuals = verify_pdf(output, [RedactedString("kolibri", "DENY_LIST")])

    assert residuals == []


def test_a_redacted_string_left_in_the_output_is_a_residual_with_its_type_and_page(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["Nothing here", "Projektet hedder kolibri"])

    residuals = verify_pdf(output, [RedactedString("kolibri", "DENY_LIST")])

    assert residuals == [Residual("DENY_LIST", 2)]


def test_the_redacted_string_check_ignores_case(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["PROJEKT KOLIBRI"])

    residuals = verify_pdf(output, [RedactedString("kolibri", "DENY_LIST")])

    assert residuals == [Residual("DENY_LIST", 1)]


def test_a_redacted_string_inside_a_longer_word_is_not_a_residual(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["Anbefalinger og transformation"])

    residuals = verify_pdf(output, [RedactedString("An", "PERSON")], entities=["EMAIL_ADDRESS"])

    assert residuals == []


def test_pii_that_detection_finds_again_is_a_residual(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["Nothing here", f"Write to {fake.email()}"])

    residuals = verify_pdf(output, [], entities=["EMAIL_ADDRESS"])

    assert residuals == [Residual("EMAIL_ADDRESS", 2)]


def test_detection_again_uses_the_same_deny_list(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["Projektet hedder kolibri"])

    residuals = verify_pdf(output, [], entities=["EMAIL_ADDRESS"], deny_terms=["kolibri"])

    assert residuals == [Residual("DENY_LIST", 1)]


def test_the_same_item_found_by_both_checks_is_reported_once(tmp_path):
    email = fake.email()
    output = make_pdf(tmp_path / "out.pdf", [f"Write to {email}"])

    residuals = verify_pdf(output, [RedactedString(email, "EMAIL_ADDRESS")], entities=["EMAIL_ADDRESS"])

    assert residuals == [Residual("EMAIL_ADDRESS", 1)]
