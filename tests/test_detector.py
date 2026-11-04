from presidio_analyzer import RecognizerResult

from pii_strip.detector import DEFAULT_THRESHOLD, find_pii_strings, without_phone_overlapping_cpr
from pii_strip.phone import DK_PHONE


def test_default_threshold_is_one_half():
    assert DEFAULT_THRESHOLD == 0.5


def test_does_not_detect_a_bare_eight_digit_number_at_the_default_threshold():
    assert find_pii_strings("Reference 12345678 oplyst.") == set()


def test_does_not_detect_a_date_written_as_eight_digits():
    assert find_pii_strings("Dato 01012024 oplyst.") == set()


def test_does_not_detect_an_amount_with_thousand_separators():
    assert find_pii_strings("Beløb 12.345.678 kr.") == set()


def test_detects_a_bare_eight_digit_number_next_to_tlf():
    assert find_pii_strings("tlf. 12345678") == {"12345678"}


def test_detects_a_prefixed_number_without_a_context_word():
    assert find_pii_strings("Ring på +45 12 34 56 78 i dag.") == {"+45 12 34 56 78"}


def test_does_not_detect_a_bare_ten_digit_cpr_number_without_context():
    assert find_pii_strings("Nummer 0101901234 oplyst.") == set()


def test_reports_a_cpr_number_once_as_a_cpr_number_and_not_as_a_phone_number():
    assert find_pii_strings("Tlf. 010190-1234 er oplyst.") == {"010190-1234"}


def test_drops_a_phone_result_that_overlaps_a_cpr_result():
    phone = RecognizerResult(DK_PHONE, 5, 13, 0.85)
    cpr = RecognizerResult("DK_CPR", 0, 11, 0.85)

    assert without_phone_overlapping_cpr([phone], [cpr]) == []


def test_keeps_a_phone_result_that_does_not_overlap_a_cpr_result():
    phone = RecognizerResult(DK_PHONE, 20, 28, 0.85)
    cpr = RecognizerResult("DK_CPR", 0, 11, 0.85)

    assert without_phone_overlapping_cpr([phone], [cpr]) == [phone]
