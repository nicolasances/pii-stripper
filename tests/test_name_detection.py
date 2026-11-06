from pii_strip import nlp
from pii_strip.detector import find_pii_strings


def test_detects_an_english_person_name():
    assert "Mary Johnson" in find_pii_strings("Mary Johnson signed the letter yesterday.")


def test_detects_a_danish_person_name():
    assert "Mette Hansen" in find_pii_strings("Mette Hansen har underskrevet brevet i går.")


def test_does_not_detect_a_location_by_default():
    assert "Aarhus" not in find_pii_strings("Mette Hansen bor i Aarhus.")


def test_detects_a_location_when_the_entity_is_enabled():
    assert "Aarhus" in find_pii_strings("Mette Hansen bor i Aarhus.", entities=["PERSON", "LOCATION"])


def test_entities_restrict_the_detected_types():
    found = find_pii_strings("Mette Hansen skriver til mette@example.com.", entities=["EMAIL_ADDRESS"])

    assert found == {"mette@example.com"}


def test_english_only_analysis_builds_an_analyzer_with_only_the_english_model(monkeypatch):
    requested = []
    real_build = nlp.build_analyzer
    monkeypatch.setattr(nlp, "build_analyzer", lambda languages: requested.append(languages) or real_build(languages))

    find_pii_strings("Mary Johnson signed the letter.", languages=["en"])

    assert requested == [("en",)]


def test_a_name_span_that_overlaps_an_email_is_not_reported_on_its_own():
    assert find_pii_strings("Skriv til mette@example.com") == {"mette@example.com"}


def test_patterns_still_fire_when_analyzing_with_one_language():
    assert find_pii_strings("Skriv til mette@example.com", languages=["en"]) == {"mette@example.com"}


def test_a_company_name_is_not_detected_as_a_person():
    found = find_pii_strings("Anna Hansen arbejder hos Novo Nordisk og Microsoft.")

    assert "Anna Hansen" in found
    assert "Novo Nordisk" not in found
    assert "Microsoft" not in found


def test_a_company_the_english_model_mistakes_for_a_person_is_not_detected():
    assert find_pii_strings("Group CFO, Tryg") == set()


def test_a_company_with_a_legal_suffix_is_not_detected():
    assert "Tryg A/S" not in find_pii_strings("Tidligere Group CEO, Tryg A/S")
