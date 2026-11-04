import pytest

from pii_strip.phone import DK_PHONE, PhoneRecognizer


def _results(text: str):
    return PhoneRecognizer().analyze(text, entities=[DK_PHONE])


def _matches(text: str) -> set[str]:
    return {text[result.start:result.end] for result in _results(text)}


def _score_of(text: str) -> float:
    results = _results(text)
    assert len(results) == 1

    return results[0].score


@pytest.mark.parametrize("number", ["12345678", "12 34 56 78", "1234 5678", "12-34-56-78"])
def test_matches_every_grouping(number):
    assert _matches(f"Tlf. {number} er åbent.") == {number}


@pytest.mark.parametrize("prefix", ["+45", "+45 ", "0045", "0045 ", "(+45)", "(+45) "])
@pytest.mark.parametrize("number", ["12345678", "12 34 56 78", "1234 5678", "12-34-56-78"])
def test_matches_every_grouping_with_a_prefix_and_includes_the_prefix(prefix, number):
    assert _matches(f"Ring på {prefix}{number} i dag.") == {f"{prefix}{number}"}


def test_matches_a_bare_number_without_context():
    assert _matches("Reference 12345678 oplyst.") == {"12345678"}


def test_does_not_match_an_amount_with_thousand_separators():
    assert _matches("Beløb 12.345.678 kr.") == set()


def test_does_not_match_eight_digits_inside_a_longer_digit_string():
    assert _matches("Tlf. 123456789") == set()
    assert _matches("Tlf. 912345678") == set()
    assert _matches("Tlf. 12 34 56 78 90") == set()


def test_scores_a_bare_number_below_the_default_threshold():
    assert _score_of("Nummer 12345678") < 0.5
    assert _score_of("Dato 01012024") < 0.5


def test_scores_a_number_with_a_context_word_above_the_default_threshold():
    assert _score_of("tlf. 12345678") >= 0.5


def test_scores_a_bare_number_lower_than_one_with_a_prefix():
    assert _score_of("Nummer 12345678") < _score_of("Nummer +45 12345678")
    assert _score_of("+45 12345678") >= 0.5


def test_recognizes_every_context_word_in_any_case():
    plain = _score_of("Nummer 12345678")

    for context in ["tlf", "Tlf.", "Telefon:", "mobil", "PHONE", "tel", "Mob"]:
        assert _score_of(f"{context} 12345678") > plain


def test_ignores_a_context_word_that_is_far_from_the_number():
    far = "Tlf " + "x" * 80 + " 12345678"

    assert _score_of(far) == _score_of("Nummer 12345678")


def test_does_not_treat_a_word_that_merely_contains_a_context_word_as_context():
    assert _score_of("Hotel 12345678") == _score_of("Nummer 12345678")
