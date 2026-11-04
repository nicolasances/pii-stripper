from presidio_analyzer import RecognizerResult
from presidio_analyzer.predefined_recognizers import EmailRecognizer

from pii_strip.cpr import DK_CPR, CprRecognizer
from pii_strip.phone import DK_PHONE, PhoneRecognizer

DEFAULT_THRESHOLD = 0.5

_email_recognizer = EmailRecognizer()
_cpr_recognizer = CprRecognizer()
_phone_recognizer = PhoneRecognizer()


def without_phone_overlapping_cpr(phone_results: list[RecognizerResult], cpr_results: list[RecognizerResult]) -> list[RecognizerResult]:
    """A CPR number contains digit runs that look like a phone number, so CPR wins on overlap."""
    return [phone for phone in phone_results if not any(phone.start < cpr.end and cpr.start < phone.end for cpr in cpr_results)]


def find_pii_strings(text: str) -> set[str]:
    """Return the distinct strings in the text that are detected as PII with a score of at least the default threshold."""
    email_results = _email_recognizer.analyze(text, entities=["EMAIL_ADDRESS"])
    cpr_results = _cpr_recognizer.analyze(text, entities=[DK_CPR])
    phone_results = without_phone_overlapping_cpr(_phone_recognizer.analyze(text, entities=[DK_PHONE]), cpr_results)

    results = [result for result in email_results + cpr_results + phone_results if result.score >= DEFAULT_THRESHOLD]

    return {text[result.start:result.end] for result in results}
