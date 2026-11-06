import json

import pytest

from pii_strip import redactor
from pii_strip.cli import main
from pii_strip.detector import KNOWN_NAME_SOURCE
from pii_strip.nlp import known_name_terms
from pii_strip.redactor import RedactedString
from pii_strip.verify import verify_pdf
from tests.support.pdf_factory import extract_text, make_pdf


@pytest.fixture
def ner_misses_names_on_pages_with(monkeypatch):
    """Simulate the NER model missing every name on a page whose text contains the marker, e.g. a short footer with no context."""
    markers: list[str] = []
    real_find = redactor.find_distinct_pii_results

    def find(text, *args):
        results = real_find(text, *args)

        if any(marker in text for marker in markers):
            return {pii: result for pii, result in results.items() if result.entity_type != "PERSON"}

        return results

    monkeypatch.setattr(redactor, "find_distinct_pii_results", find)

    return markers.append


def test_the_terms_of_a_name_are_the_full_name_and_its_parts():
    assert known_name_terms(["Mette Jensen"]) == {"Mette Jensen", "Mette", "Jensen"}


def test_a_salutation_in_the_name_span_is_not_a_part():
    assert known_name_terms(["Kære Mette Hansen", "Dear Ryan Mendez"]) == {"Kære Mette Hansen", "Mette", "Hansen", "Dear Ryan Mendez", "Ryan", "Mendez"}


def test_a_one_word_name_that_is_a_salutation_or_title_is_not_spread():
    assert known_name_terms(["Vedr", "Hej", "Jensen"]) == {"Jensen"}


def test_a_job_title_in_the_name_span_is_not_a_part():
    assert known_name_terms(["Ryan Mendez Head", "Direktør Mette Jensen"]) == {"Ryan Mendez Head", "Ryan", "Mendez", "Direktør Mette Jensen", "Mette", "Jensen"}


def test_a_job_title_next_to_a_name_is_not_redacted_elsewhere(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Ryan Mendez Head of Innovation", "Head of Product is hiring."])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert exit_code == 0
    assert "Mendez" not in extract_text(output)
    assert "Head of Innovation" in extract_text(output)
    assert "Head of Product" in extract_text(output)


def test_lowercase_words_in_the_name_span_are_not_parts():
    assert known_name_terms(["Vi har talt med Mette"]) == {"Vi har talt med Mette", "Mette"}


def test_initials_and_parts_shorter_than_3_characters_are_not_parts():
    assert known_name_terms(["M. Jensen", "Bo Ek"]) == {"M. Jensen", "Jensen", "Bo Ek"}


def test_a_double_surname_is_one_part():
    assert known_name_terms(["Mette Hansen-Berg"]) == {"Mette Hansen-Berg", "Mette", "Hansen-Berg"}


def test_an_allowed_term_is_not_a_known_name_term():
    assert known_name_terms(["Mette Jensen"], allow_terms=["jensen"]) == {"Mette Jensen", "Mette"}


def test_a_surname_alone_in_a_footer_is_redacted_when_the_full_name_is_on_another_page(tmp_path, ner_misses_names_on_pages_with):
    ner_misses_names_on_pages_with("Side 2")
    source = make_pdf(tmp_path / "in.pdf", ["Mette Jensen skrev rapporten om budgettet.", "Budgettet er godkendt. Side 2 · Jensen"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert exit_code == 0
    assert "Jensen" not in extract_text(output)
    assert "Side 2" in extract_text(output)


def test_a_surname_on_an_earlier_page_is_redacted_when_the_full_name_comes_later(tmp_path, ner_misses_names_on_pages_with):
    ner_misses_names_on_pages_with("Side 1")
    source = make_pdf(tmp_path / "in.pdf", ["Indledning. Side 1 · Jensen", "Mette Jensen skrev rapporten om budgettet."])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert exit_code == 0
    assert "Jensen" not in extract_text(output)


def test_a_full_name_the_model_misses_on_one_page_is_redacted_there_too(tmp_path, ner_misses_names_on_pages_with):
    ner_misses_names_on_pages_with("Bilag")
    source = make_pdf(tmp_path / "in.pdf", ["Mette Jensen skrev rapporten om budgettet.", "Bilag: tabel udfyldt af Mette Jensen"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert exit_code == 0
    assert "Mette" not in extract_text(output)
    assert "Jensen" not in extract_text(output)


def test_a_surname_that_is_also_a_common_word_is_only_redacted_in_the_same_case_or_all_capitals(tmp_path, ner_misses_names_on_pages_with):
    ner_misses_names_on_pages_with("Side 2")
    source = make_pdf(tmp_path / "in.pdf", ["Mette Skov skrev rapporten om budgettet.", "Turen gik gennem en skov. Side 2 · Skov · SKOV"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert exit_code == 0
    assert "gennem en skov" in extract_text(output)
    assert "Skov" not in extract_text(output)
    assert "SKOV" not in extract_text(output)


def test_an_allowed_surname_is_not_redacted_elsewhere(tmp_path, ner_misses_names_on_pages_with):
    ner_misses_names_on_pages_with("Side 2")
    allow = tmp_path / "allow.txt"
    allow.write_text("Jensen\n")
    source = make_pdf(tmp_path / "in.pdf", ["Mette Jensen skrev rapporten om budgettet.", "Budgettet er godkendt. Side 2 · Jensen"])
    output = tmp_path / "out.pdf"

    main([str(source), "-o", str(output), "--allow", str(allow), "--quiet"])

    assert "Side 2 · Jensen" in extract_text(output)
    assert "Mette Jensen" not in extract_text(output)


def test_a_known_name_hit_is_reported_as_person_with_the_known_name_source(tmp_path, ner_misses_names_on_pages_with):
    ner_misses_names_on_pages_with("Side 2")
    source = make_pdf(tmp_path / "in.pdf", ["Mette Jensen skrev rapporten om budgettet.", "Budgettet er godkendt. Side 2 · Jensen"])
    report = tmp_path / "report.json"

    main([str(source), "-o", str(tmp_path / "out.pdf"), "--report", str(report), "--quiet"])

    page_2 = [finding for finding in json.loads(report.read_text())["findings"] if finding["page"] == 2]
    assert [(finding["entity_type"], finding["source"], len(finding["areas"])) for finding in page_2] == [("PERSON", KNOWN_NAME_SOURCE, 1)]


def test_verification_only_flags_an_exact_case_string_in_the_same_case_or_all_capitals(tmp_path):
    output = make_pdf(tmp_path / "out.pdf", ["Turen gik gennem en skov."])

    residuals = verify_pdf(output, [RedactedString("Skov", "PERSON", exact_case=True)], entities=["EMAIL_ADDRESS"])

    assert residuals == []
