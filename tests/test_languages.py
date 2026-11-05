import pytest
from presidio_analyzer import RecognizerResult

from pii_strip.nlp import ModelMissingError, SUPPORTED_ENTITIES, is_plausible_name, merge_results, parse_entities, parse_languages, require_models


def test_languages_default_to_danish_and_english():
    assert parse_languages(None) == ["da", "en"]


def test_parses_a_comma_separated_language_list():
    assert parse_languages("en") == ["en"]


def test_rejects_an_unsupported_language():
    with pytest.raises(ValueError, match="fr"):
        parse_languages("da,fr")


def test_entities_default_to_person_and_the_pattern_types_but_not_location():
    entities = parse_entities(None)

    assert "PERSON" in entities
    assert "LOCATION" not in entities


def test_location_can_be_enabled_through_entities():
    assert parse_entities("PERSON,LOCATION") == ["PERSON", "LOCATION"]


def test_rejects_an_unknown_entity_type():
    with pytest.raises(ValueError, match="CREDIT_CARD"):
        parse_entities("PERSON,CREDIT_CARD")


def test_supported_entities_include_all_pattern_types():
    assert {"EMAIL_ADDRESS", "DK_CPR", "DK_PHONE", "PERSON", "LOCATION"} <= set(SUPPORTED_ENTITIES)


def test_a_missing_model_raises_an_error_with_install_instructions():
    with pytest.raises(ModelMissingError, match="pip install"):
        require_models(["en"], is_installed=lambda name: False)


def test_installed_models_pass_the_check():
    require_models(["da", "en"], is_installed=lambda name: True)


def test_merging_keeps_the_highest_score_of_overlapping_results():
    low = RecognizerResult("PERSON", 0, 10, 0.5)
    high = RecognizerResult("PERSON", 2, 12, 0.9)

    assert merge_results([low, high]) == [high]


def test_merging_combines_non_overlapping_results():
    first = RecognizerResult("PERSON", 0, 5, 0.8)
    second = RecognizerResult("PERSON", 10, 15, 0.7)

    assert merge_results([second, first]) == [first, second]


def test_a_span_with_a_digit_is_not_a_plausible_name():
    assert not is_plausible_name("Nummer 290200-1234")


def test_a_span_starting_with_a_lowercase_letter_is_not_a_plausible_name():
    assert not is_plausible_name("tlf")


def test_a_capitalized_name_is_plausible():
    assert is_plausible_name("Mette Hansen")


def test_an_all_caps_name_is_plausible():
    assert is_plausible_name("METTE HANSEN")


def test_merging_keeps_overlapping_results_of_different_entity_types_apart():
    person = RecognizerResult("PERSON", 0, 16, 0.85)
    location = RecognizerResult("LOCATION", 10, 16, 0.85)

    assert merge_results([person, location]) == [person, location]
