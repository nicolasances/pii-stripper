from presidio_analyzer import RecognizerResult
from presidio_analyzer.predefined_recognizers import EmailRecognizer

from pii_strip.cpr import DK_CPR, CprRecognizer
from pii_strip.nlp import DEFAULT_ENTITIES, SUPPORTED_LANGUAGES, find_named_entities
from pii_strip.phone import DK_PHONE, PhoneRecognizer

DEFAULT_THRESHOLD = 0.5

_email_recognizer = EmailRecognizer()
_cpr_recognizer = CprRecognizer()
_phone_recognizer = PhoneRecognizer()


def without_phone_overlapping_cpr(phone_results: list[RecognizerResult], cpr_results: list[RecognizerResult]) -> list[RecognizerResult]:
    """A CPR number contains digit runs that look like a phone number, so CPR wins on overlap."""
    return [phone for phone in phone_results if not any(phone.start < cpr.end and cpr.start < phone.end for cpr in cpr_results)]


def find_pii_results(text: str, languages: list[str] | None = None, entities: list[str] | None = None) -> list[RecognizerResult]:
    """Return the findings in the text with a score of at least the default threshold.
    Only the listed entity types are detected (default: PERSON and the pattern types), analyzed with the listed languages (default: da and en)."""
    languages = languages or list(SUPPORTED_LANGUAGES)
    entities = entities or list(DEFAULT_ENTITIES)

    email_results = _email_recognizer.analyze(text, entities=["EMAIL_ADDRESS"]) if "EMAIL_ADDRESS" in entities else []
    cpr_results = _cpr_recognizer.analyze(text, entities=[DK_CPR])
    phone_results = without_phone_overlapping_cpr(_phone_recognizer.analyze(text, entities=[DK_PHONE]), cpr_results) if DK_PHONE in entities else []
    cpr_results = cpr_results if DK_CPR in entities else []
    name_results = find_named_entities(text, languages, entities)

    pattern_results = [result for result in email_results + cpr_results + phone_results if result.score >= DEFAULT_THRESHOLD]
    name_results = [name for name in name_results if not any(name.start < pattern.end and pattern.start < name.end for pattern in pattern_results)]

    return [result for result in pattern_results + name_results if result.score >= DEFAULT_THRESHOLD]


def find_pii_strings(text: str, languages: list[str] | None = None, entities: list[str] | None = None) -> set[str]:
    """Return the distinct strings in the text that are detected as PII."""
    return {text[result.start:result.end] for result in find_pii_results(text, languages, entities)}
