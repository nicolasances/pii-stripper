from pii_strip.cpr import DK_CPR, CprRecognizer
from pii_strip.detector import find_pii_strings


def test_detects_a_cpr_number_with_a_dash():
    assert find_pii_strings("CPR 010190-1234 er oplyst.") == {"010190-1234"}


def test_detects_a_cpr_number_with_a_space():
    assert find_pii_strings("Fødselsnummer 010190 1234 er oplyst.") == {"010190 1234"}


def test_detects_a_cpr_number_in_english_text():
    assert find_pii_strings("The applicant's number is 150385-4321.") == {"150385-4321"}


def test_does_not_detect_a_day_that_does_not_exist():
    assert find_pii_strings("Nummer 320199-1234") == set()


def test_does_not_detect_a_month_that_does_not_exist():
    assert find_pii_strings("Nummer 011399-1234") == set()


def test_does_not_detect_the_day_zero():
    assert find_pii_strings("Nummer 000190-1234") == set()


def test_does_not_detect_31_in_a_30_day_month():
    assert find_pii_strings("Nummer 310490-1234") == set()


def test_detects_29_february_in_a_leap_year():
    assert find_pii_strings("Nummer 290200-1234") == {"290200-1234"}


def test_does_not_detect_29_february_in_a_year_that_is_never_a_leap_year():
    assert find_pii_strings("Nummer 290201-1234") == set()


def test_detects_a_valid_date_cpr_number_that_fails_modulus_11():
    # 010190-1234 has a weighted digit sum that is not divisible by 11
    assert find_pii_strings("Nummer 010190-1234") == {"010190-1234"}


def test_does_not_detect_a_cpr_shaped_substring_inside_a_longer_digit_string():
    assert find_pii_strings("Reference 9010190-12345") == set()
    assert find_pii_strings("Reference 010190-12345") == set()


def test_does_not_detect_a_dashed_number_with_a_short_suffix():
    assert find_pii_strings("Nummer 010190-123") == set()


def _score_of(text: str) -> float:
    results = CprRecognizer().analyze(text, entities=[DK_CPR])
    assert len(results) == 1

    return results[0].score


def test_detects_an_undelimited_cpr_number():
    assert find_pii_strings("CPR 0101901234 oplyst.") == {"0101901234"}


def test_does_not_detect_a_ten_digit_number_without_a_valid_date():
    assert find_pii_strings("Konto 9999999999") == set()


def test_does_not_detect_an_undelimited_number_inside_a_longer_digit_string():
    assert find_pii_strings("Konto 010190123456") == set()
    assert find_pii_strings("Konto 90101901234") == set()


def test_scores_an_undelimited_number_lower_than_a_delimited_one():
    assert _score_of("Nummer 0101901234") < _score_of("Nummer 010190-1234")


def test_raises_the_score_of_an_undelimited_number_when_a_context_word_precedes_it():
    assert _score_of("CPR 0101901234") > _score_of("Nummer 0101901234")


def test_recognizes_every_context_word_in_any_case():
    plain = _score_of("Nummer 0101901234")

    for context in ["CPR-nr:", "personnummer", "Fødselsdato", "cpr"]:
        assert _score_of(f"{context} 0101901234") > plain


def test_ignores_a_context_word_that_is_far_from_the_number():
    far = "CPR " + "x" * 80 + " 0101901234"

    assert _score_of(far) == _score_of("Nummer 0101901234")
