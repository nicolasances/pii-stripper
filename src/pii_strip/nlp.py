from functools import lru_cache
from typing import Callable

import spacy.util
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NerModelConfiguration, SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

SUPPORTED_LANGUAGES = ["da", "en"]
MODELS = {"da": "da_core_news_md", "en": "en_core_web_md"}
SUPPORTED_ENTITIES = ["PERSON", "LOCATION", "EMAIL_ADDRESS", "DK_CPR", "DK_PHONE"]
DEFAULT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "DK_CPR", "DK_PHONE"]
NER_ENTITIES = ["PERSON", "LOCATION"]
# The Danish model labels people PER and places LOC; the English model uses PERSON, GPE and LOC. Organizations are kept only to veto mislabelled people and places; every other label is ignored.
ORGANIZATION = "ORGANIZATION"
_LABEL_TO_ENTITY = {"PER": "PERSON", "PERSON": "PERSON", "LOC": "LOCATION", "GPE": "LOCATION", "ORG": ORGANIZATION}
_IGNORED_LABELS = ["MISC", "DATE", "CARDINAL", "NORP", "FAC", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL"]


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


def require_models(languages: list[str], is_installed: Callable[[str], bool] | None = None) -> None:
    """Fail before any analysis if a model is missing. A model is never downloaded at runtime."""
    is_installed = is_installed or spacy.util.is_package
    missing = [MODELS[language] for language in languages if not is_installed(MODELS[language])]

    if missing:
        raise ModelMissingError(f"the NLP model(s) {', '.join(missing)} are not installed. Install them with: pip install {' '.join(missing)} (see the README for the pinned download URLs). pii-strip never downloads a model itself.")


def is_plausible_name(span: str) -> bool:
    """The NER models also tag labels and amounts in short snippets (e.g. 'tlf', 'Nummer 0101901234'). A name or place has no digit and starts with an uppercase letter."""
    return span[:1].isupper() and not any(character.isdigit() for character in span)


MIN_ORGANIZATION_OVERLAP = 0.6
LANGUAGE_KEY = "language"


def _mostly_the_same_span(first: RecognizerResult, second: RecognizerResult) -> bool:
    shared = min(first.end, second.end) - max(first.start, second.start)

    return shared > 0 and shared / max(first.end - first.start, second.end - second.start) >= MIN_ORGANIZATION_OVERLAP


def without_organizations(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Company names are not personal data. One model often labels a company correctly while the other calls it a person (e.g. 'Novo Nordisk', 'Tryg'),
    so a person or place that mostly coincides with an organization found by any model is dropped, and the organizations themselves are never reported.
    A person inside a much longer organization span is kept: the models sometimes tag a whole clause as an organization, and a missed name is worse than a kept company."""
    organizations = [result for result in results if result.entity_type == ORGANIZATION]

    return [result for result in results if result.entity_type != ORGANIZATION and not any(_mostly_the_same_span(result, org) for org in organizations)]


def merge_results(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Merge overlapping findings of the same entity type (e.g. from different languages) into one, keeping the highest score."""
    merged: list[RecognizerResult] = []

    for result in sorted(results, key=lambda r: (r.start, r.end)):
        previous = next((kept for kept in reversed(merged) if kept.entity_type == result.entity_type), None)

        if previous is not None and result.start < previous.end:
            if result.score > previous.score:
                merged[merged.index(previous)] = result
        else:
            merged.append(result)

    return merged


def _with_language(result: RecognizerResult, language: str) -> RecognizerResult:
    """Record which language's model found the result, for the report (F09)."""
    result.recognition_metadata = {**(result.recognition_metadata or {}), LANGUAGE_KEY: language}

    return result


@lru_cache(maxsize=None)
def build_analyzer(languages: tuple[str, ...]) -> AnalyzerEngine:
    """An analyzer with an explicit spaCy model per language. No default model is ever loaded or downloaded."""
    require_models(list(languages))

    ner_configuration = NerModelConfiguration(model_to_presidio_entity_mapping=_LABEL_TO_ENTITY, labels_to_ignore=_IGNORED_LABELS)
    nlp_engine = SpacyNlpEngine(models=[{"lang_code": language, "model_name": MODELS[language]} for language in languages], ner_model_configuration=ner_configuration)
    registry = RecognizerRegistry(supported_languages=list(languages))

    for language in languages:
        registry.add_recognizer(SpacyRecognizer(supported_language=language, supported_entities=NER_ENTITIES + [ORGANIZATION]))

    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=list(languages))


def find_named_entities(text: str, languages: list[str], entities: list[str]) -> list[RecognizerResult]:
    """Analyze the text once per language and merge the findings. The pattern recognizers run separately, because they do not depend on the language."""
    wanted = [entity for entity in entities if entity in NER_ENTITIES]

    if not wanted:
        return []

    analyzer = build_analyzer(tuple(languages))
    results = [_with_language(result, language) for language in languages for result in analyzer.analyze(text, language=language, entities=wanted + [ORGANIZATION])]

    plausible = [result for result in results if result.entity_type == ORGANIZATION or is_plausible_name(text[result.start:result.end])]

    return without_organizations(merge_results(plausible))
