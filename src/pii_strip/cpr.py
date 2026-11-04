import re
from calendar import isleap

from presidio_analyzer import Pattern, PatternRecognizer

DK_CPR = "DK_CPR"
DELIMITED_SCORE = 0.85
UNDELIMITED_SCORE = 0.3
CONTEXT_SCORE = 0.85
CONTEXT_WINDOW = 30
CONTEXT_WORDS = ["cpr", "cpr-nr", "personnummer", "fødselsdato"]

# The digit look-arounds stop a match inside a longer digit string
_DELIMITED_CPR = r"(?<!\d)\d{6}[- ]\d{4}(?!\d)"
_UNDELIMITED_CPR = r"(?<!\d)\d{10}(?!\d)"

_DAYS_IN_MONTH = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
_CONTEXT_REGEX = re.compile("|".join(re.escape(word) for word in CONTEXT_WORDS), re.IGNORECASE)


def _is_valid_birth_date(day: int, month: int, year: int) -> bool:
    if month not in _DAYS_IN_MONTH or day < 1:
        return False

    if month == 2 and day == 29:
        return isleap(1900 + year) or isleap(2000 + year)

    return day <= (28 if month == 2 else _DAYS_IN_MONTH[month])


class CprRecognizer(PatternRecognizer):
    """Recognizes Danish CPR numbers. The first six digits must be a valid date. The modulus-11 check is deliberately not used."""

    def __init__(self):
        patterns = [Pattern(name="dk_cpr_delimited", regex=_DELIMITED_CPR, score=DELIMITED_SCORE), Pattern(name="dk_cpr_undelimited", regex=_UNDELIMITED_CPR, score=UNDELIMITED_SCORE)]
        super().__init__(supported_entity=DK_CPR, patterns=patterns, supported_language=None)

    def validate_result(self, pattern_text: str) -> bool | None:
        digits = pattern_text[:6]

        # Returning True would make Presidio raise the score to the maximum, so a valid date returns None to keep the pattern score
        if _is_valid_birth_date(int(digits[0:2]), int(digits[2:4]), int(digits[4:6])):
            return None

        return False

    def analyze(self, text, entities=None, nlp_artifacts=None, regex_flags=None):
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)

        for result in results:
            if _CONTEXT_REGEX.search(text[max(0, result.start - CONTEXT_WINDOW):result.start]):
                result.score = max(result.score, CONTEXT_SCORE)

        return results
