from presidio_analyzer.predefined_recognizers import EmailRecognizer

_email_recognizer = EmailRecognizer()


def find_pii_strings(text: str) -> set[str]:
    """Return the distinct strings in the text that are detected as PII."""
    results = _email_recognizer.analyze(text, entities=["EMAIL_ADDRESS"])

    return {text[result.start:result.end] for result in results}
