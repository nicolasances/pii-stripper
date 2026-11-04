from presidio_analyzer.predefined_recognizers import EmailRecognizer

from pii_strip.cpr import DK_CPR, CprRecognizer

_email_recognizer = EmailRecognizer()
_cpr_recognizer = CprRecognizer()


def find_pii_strings(text: str) -> set[str]:
    """Return the distinct strings in the text that are detected as PII."""
    results = _email_recognizer.analyze(text, entities=["EMAIL_ADDRESS"]) + _cpr_recognizer.analyze(text, entities=[DK_CPR])

    return {text[result.start:result.end] for result in results}
