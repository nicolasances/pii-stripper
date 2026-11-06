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


# The NER models tag invented names and sentence starts, so the tests of the lists keep them out of the way
ENTITIES_WITHOUT_NER = ["EMAIL_ADDRESS", "DK_CPR", "DK_PHONE"]


def test_a_deny_term_is_found_even_though_nothing_else_is_detected():
    assert find_pii_strings("Kontakt Zyxwv Qrstu i dag.", entities=ENTITIES_WITHOUT_NER, deny_terms=["Zyxwv Qrstu"]) == {"Zyxwv Qrstu"}


def test_a_deny_term_matches_case_insensitively_and_keeps_the_case_of_the_text():
    assert find_pii_strings("Kontakt ZYXWV og zyxwv i dag.", entities=ENTITIES_WITHOUT_NER, deny_terms=["Zyxwv"]) == {"ZYXWV", "zyxwv"}


def test_a_deny_term_matches_whole_words_only():
    assert find_pii_strings("Zyxwvs og Xzyxwv er ikke det samme.", entities=ENTITIES_WITHOUT_NER, deny_terms=["Zyxwv"]) == set()


def test_a_deny_term_matches_across_a_line_break():
    assert find_pii_strings("Kontakt Zyxwv\nQrstu i dag.", entities=ENTITIES_WITHOUT_NER, deny_terms=["Zyxwv Qrstu"]) == {"Zyxwv\nQrstu"}


def test_a_deny_term_is_matched_literally_not_as_a_regular_expression():
    assert find_pii_strings("Se a.c og abc.", entities=ENTITIES_WITHOUT_NER, deny_terms=["a.c"]) == {"a.c"}


def test_a_deny_term_survives_the_maximum_threshold():
    assert find_pii_strings("Kontakt Zyxwv Qrstu i dag.", entities=ENTITIES_WITHOUT_NER, threshold=1.0, deny_terms=["Zyxwv Qrstu"]) == {"Zyxwv Qrstu"}


def test_an_allowed_term_is_not_reported():
    assert find_pii_strings("Skriv til info@acme.dk", entities=ENTITIES_WITHOUT_NER, allow_terms=["info@acme.dk"]) == set()


def test_an_allowed_term_matches_the_finding_case_insensitively():
    assert find_pii_strings("Skriv til Info@ACME.dk", entities=ENTITIES_WITHOUT_NER, allow_terms=["info@acme.dk"]) == set()


def test_a_finding_that_only_contains_an_allowed_term_is_kept():
    assert find_pii_strings("Skriv til info@acme.dk", entities=ENTITIES_WITHOUT_NER, allow_terms=["acme"]) == {"info@acme.dk"}


def test_a_term_on_both_lists_is_reported():
    assert find_pii_strings("Kontakt Zyxwv Qrstu i dag.", entities=ENTITIES_WITHOUT_NER, allow_terms=["Zyxwv Qrstu"], deny_terms=["zyxwv qrstu"]) == {"Zyxwv Qrstu"}


def test_a_higher_threshold_drops_findings_below_it():
    assert find_pii_strings("tlf. 12345678", entities=ENTITIES_WITHOUT_NER) == {"12345678"}
    assert find_pii_strings("tlf. 12345678", entities=ENTITIES_WITHOUT_NER, threshold=0.99) == set()


def test_a_lower_threshold_keeps_weaker_findings():
    assert find_pii_strings("Reference 12345678 oplyst.", threshold=0.0) != set()
