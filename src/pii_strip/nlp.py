from typing import Callable

import spacy.util
from presidio_analyzer import RecognizerResult

SUPPORTED_LANGUAGES = ["da", "en"]
MODELS = {"da": "da_core_news_md", "en": "en_core_web_md"}
SUPPORTED_ENTITIES = ["PERSON", "LOCATION", "EMAIL_ADDRESS", "DK_CPR", "DK_PHONE"]
DEFAULT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "DK_CPR", "DK_PHONE"]


class ModelMissingError(Exception):
    """A required NLP model is not installed. The message says how to install it."""


def parse_languages(value: str | None) -> list[str]:
    if value is None:
        return list(SUPPORTED_LANGUAGES)

    languages = [language.strip() for language in value.split(",") if language.strip()]
    unsupported = [language for language in languages if language not in SUPPORTED_LANGUAGES]

    if unsupported or not languages:
        raise ValueError(f"unsupported language(s): {', '.join(unsupported) or value!r}; supported: {', '.join(SUPPORTED_LANGUAGES)}")

    return languages


def parse_entities(value: str | None) -> list[str]:
    if value is None:
        return list(DEFAULT_ENTITIES)

    entities = [entity.strip() for entity in value.split(",") if entity.strip()]
    unknown = [entity for entity in entities if entity not in SUPPORTED_ENTITIES]

    if unknown or not entities:
        raise ValueError(f"unknown entity type(s): {', '.join(unknown) or value!r}; supported: {', '.join(SUPPORTED_ENTITIES)}")

    return entities


def require_models(languages: list[str], is_installed: Callable[[str], bool] = spacy.util.is_package) -> None:
    """Fail before any analysis if a model is missing. A model is never downloaded at runtime."""
    missing = [MODELS[language] for language in languages if not is_installed(MODELS[language])]

    if missing:
        raise ModelMissingError(f"the NLP model(s) {', '.join(missing)} are not installed. Install them with: pip install {' '.join(missing)} (see the README for the pinned download URLs). pii-strip never downloads a model itself.")


def merge_results(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Merge overlapping findings (e.g. from different languages) into one, keeping the highest score."""
    merged: list[RecognizerResult] = []

    for result in sorted(results, key=lambda r: (r.start, r.end)):
        if merged and result.start < merged[-1].end:
            if result.score > merged[-1].score:
                merged[-1] = result
        else:
            merged.append(result)

    return merged
