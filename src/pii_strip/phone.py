import re

from presidio_analyzer import Pattern, PatternRecognizer

DK_PHONE = "DK_PHONE"
BARE_SCORE = 0.3
PREFIX_OR_CONTEXT_SCORE = 0.85
CONTEXT_WINDOW = 30
CONTEXT_WORDS = ["tlf", "telefon", "mobil", "phone", "tel", "mob"]

_PREFIX = r"(?:(?:\+45|0045)[ ]?|\(\+45\)[ ]?)"
_NUMBER = r"(?:\d{8}|\d{2}([ -])\d{2}\1\d{2}\1\d{2}|\d{4} \d{4})"
# The look-arounds stop a match inside a longer digit string, including a longer run of two-digit groups
_PHONE = rf"(?<![\d+])(?:{_PREFIX})?{_NUMBER}(?!\d)(?![ -]\d{{2}}(?!\d))"

_PREFIX_REGEX = re.compile(rf"^{_PREFIX}")
_CONTEXT_REGEX = re.compile(r"\b(?:" + "|".join(re.escape(word) for word in CONTEXT_WORDS) + ")", re.IGNORECASE)


class PhoneRecognizer(PatternRecognizer):
    """Recognizes Danish phone numbers: 8 digits in a few groupings, with an optional +45, 0045 or (+45) prefix.
    A number gets a high score with a prefix or a context word before it, and a low score otherwise."""

    def __init__(self):
        super().__init__(supported_entity=DK_PHONE, patterns=[Pattern(name="dk_phone", regex=_PHONE, score=BARE_SCORE)], supported_language=None)

    def analyze(self, text, entities=None, nlp_artifacts=None, regex_flags=None):
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)

        for result in results:
            has_prefix = _PREFIX_REGEX.match(text[result.start:result.end]) is not None
            has_context = _CONTEXT_REGEX.search(text[max(0, result.start - CONTEXT_WINDOW):result.start]) is not None

            if has_prefix or has_context:
                result.score = PREFIX_OR_CONTEXT_SCORE

        return results
