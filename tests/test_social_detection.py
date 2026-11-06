import pytest

from pii_strip.cli import main
from pii_strip.detector import find_pii_strings
from pii_strip.nlp import DEFAULT_ENTITIES, SUPPORTED_ENTITIES, parse_entities
from pii_strip.social import SOCIAL_PROFILE, SocialProfileRecognizer
from tests.support.pdf_factory import extract_text, make_pdf


def _matches(text: str) -> set[str]:
    return {text[result.start:result.end] for result in SocialProfileRecognizer().analyze(text, entities=[SOCIAL_PROFILE])}


@pytest.mark.parametrize("profile", ["linkedin.com/in/mette-jensen-1a2b3c", "facebook.com/mette.jensen", "instagram.com/mette_jensen", "x.com/mettejensen", "twitter.com/mettejensen", "github.com/mjensen", "tiktok.com/@mette.jensen"])
def test_matches_a_profile_on_every_supported_platform(profile):
    assert _matches(f"Profil: {profile} (privat)") == {profile}


@pytest.mark.parametrize("prefix", ["https://", "http://", "www.", "https://www.", "https://dk."])
def test_includes_the_scheme_and_subdomain_in_the_match(prefix):
    assert _matches(f"Se {prefix}linkedin.com/in/mette-jensen for mere.") == {f"{prefix}linkedin.com/in/mette-jensen"}


def test_includes_a_trailing_slash_but_not_the_sentence_punctuation():
    assert _matches("Se https://www.linkedin.com/in/mette-jensen/. Tak") == {"https://www.linkedin.com/in/mette-jensen/"}


def test_does_not_match_a_platform_without_a_profile():
    assert _matches("Vi er på linkedin.com og facebook.com.") == set()


def test_does_not_match_a_domain_that_only_ends_like_a_platform():
    assert _matches("Se box.com/mette og mylinkedin.com/in/mette.") == set()


def test_does_not_match_a_linkedin_company_page():
    assert _matches("Følg linkedin.com/company/acme") == set()


def test_social_profile_is_supported_and_on_by_default():
    assert SOCIAL_PROFILE in SUPPORTED_ENTITIES
    assert SOCIAL_PROFILE in DEFAULT_ENTITIES
    assert parse_entities(SOCIAL_PROFILE) == [SOCIAL_PROFILE]


def test_detection_finds_a_profile_with_the_default_entities():
    assert "https://www.linkedin.com/in/mette-jensen" in find_pii_strings("Kontakt: https://www.linkedin.com/in/mette-jensen")


def test_detection_skips_profiles_when_the_entity_is_not_requested():
    assert find_pii_strings("Kontakt: linkedin.com/in/mette-jensen", entities=["EMAIL_ADDRESS"]) == set()


def test_the_allow_list_keeps_a_profile():
    assert find_pii_strings("Kontakt: github.com/acme-bot", allow_terms=["github.com/acme-bot"]) == set()


def test_the_cli_redacts_the_whole_profile_url(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Kontakt mig: https://www.linkedin.com/in/mette-jensen-1a2b3c"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert exit_code == 0
    assert "linkedin.com" not in extract_text(output)
    assert "mette-jensen" not in extract_text(output)
