import re

from presidio_analyzer import RecognizerResult
from presidio_analyzer.predefined_recognizers import EmailRecognizer

from pii_strip.cpr import DK_CPR, CprRecognizer
from pii_strip.nlp import DEFAULT_ENTITIES, LANGUAGE_KEY, NER_ENTITIES, SUPPORTED_LANGUAGES, find_named_entities
from pii_strip.phone import DK_PHONE, PhoneRecognizer
from pii_strip.term_lists import DEFAULT_THRESHOLD

DENY_LIST = "DENY_LIST"
DENY_LIST_SOURCE = "deny_list"
NER_SOURCE = "ner"
PATTERN_SOURCE = "pattern"

_email_recognizer = EmailRecognizer()
_cpr_recognizer = CprRecognizer()
_phone_recognizer = PhoneRecognizer()


def without_phone_overlapping_cpr(phone_results: list[RecognizerResult], cpr_results: list[RecognizerResult]) -> list[RecognizerResult]:
    """A CPR number contains digit runs that look like a phone number, so CPR wins on overlap."""
    return [phone for phone in phone_results if not any(phone.start < cpr.end and cpr.start < phone.end for cpr in cpr_results)]


def find_deny_list_results(text: str, deny_terms: list[str]) -> list[RecognizerResult]:
    """Every whole-word, case-insensitive occurrence of a deny term is a finding with a score of 1.0. Whitespace inside a term also matches a line break."""
    results = []

    for term in deny_terms:
        pattern = r"\s+".join(re.escape(word) for word in term.split())

        for match in re.finditer(rf"(?<!\w){pattern}(?!\w)", text, flags=re.IGNORECASE):
            results.append(RecognizerResult(DENY_LIST, match.start(), match.end(), 1.0, recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: DENY_LIST_SOURCE}))

    return results


def source_of(result: RecognizerResult) -> str:
    """How the result was found: by the deny list, by a language model (NER) or by a pattern."""
    if result.entity_type == DENY_LIST:
        return DENY_LIST_SOURCE

    return NER_SOURCE if result.entity_type in NER_ENTITIES else PATTERN_SOURCE


def language_of(result: RecognizerResult) -> str | None:
    """The language whose model found the result, or None for the language-independent patterns and the deny list."""
    return (result.recognition_metadata or {}).get(LANGUAGE_KEY)


def find_pii_results(text: str, languages: list[str] | None = None, entities: list[str] | None = None, threshold: float = DEFAULT_THRESHOLD, allow_terms: list[str] | None = None, deny_terms: list[str] | None = None) -> list[RecognizerResult]:
    """Return the findings in the text with a score of at least the threshold (default 0.5).
    Only the listed entity types are detected (default: PERSON and the pattern types), analyzed with the listed languages (default: da and en).
    A finding whose text equals an allow term (ignoring case) is dropped. Deny terms are always findings, and win over the allow list and the threshold."""
    languages = languages or list(SUPPORTED_LANGUAGES)
    entities = entities or list(DEFAULT_ENTITIES)
    allowed = {term.casefold() for term in allow_terms or []}

    email_results = _email_recognizer.analyze(text, entities=["EMAIL_ADDRESS"]) if "EMAIL_ADDRESS" in entities else []
    cpr_results = _cpr_recognizer.analyze(text, entities=[DK_CPR])
    phone_results = without_phone_overlapping_cpr(_phone_recognizer.analyze(text, entities=[DK_PHONE]), cpr_results) if DK_PHONE in entities else []
    cpr_results = cpr_results if DK_CPR in entities else []
    name_results = find_named_entities(text, languages, entities)

    pattern_results = [result for result in email_results + cpr_results + phone_results if result.score >= threshold]
    name_results = [name for name in name_results if not any(name.start < pattern.end and pattern.start < name.end for pattern in pattern_results)]
    detected = [result for result in pattern_results + name_results if result.score >= threshold and text[result.start:result.end].strip().casefold() not in allowed]

    return detected + find_deny_list_results(text, deny_terms or [])


def find_pii_strings(text: str, languages: list[str] | None = None, entities: list[str] | None = None, threshold: float = DEFAULT_THRESHOLD, allow_terms: list[str] | None = None, deny_terms: list[str] | None = None) -> set[str]:
    """Return the distinct strings in the text that are detected as PII."""
    return {text[result.start:result.end] for result in find_pii_results(text, languages, entities, threshold, allow_terms, deny_terms)}


def find_distinct_pii_results(text: str, languages: list[str] | None = None, entities: list[str] | None = None, threshold: float = DEFAULT_THRESHOLD, allow_terms: list[str] | None = None, deny_terms: list[str] | None = None) -> dict[str, RecognizerResult]:
    """Return the distinct strings in the text that are detected as PII, each with a finding for it (entity type, score, source)."""
    return {text[result.start:result.end]: result for result in find_pii_results(text, languages, entities, threshold, allow_terms, deny_terms)}
