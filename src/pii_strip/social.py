from presidio_analyzer import Pattern, PatternRecognizer

SOCIAL_PROFILE = "SOCIAL_PROFILE"
PROFILE_SCORE = 0.9

_SCHEME_AND_SUBDOMAIN = r"(?:https?://)?(?:(?:www|[a-z]{2})\.)?"
_PLATFORMS = r"(?:linkedin\.com/in/|facebook\.com/|instagram\.com/|(?:x|twitter)\.com/|github\.com/|tiktok\.com/@)"
# The profile name may contain dots, but doesn't end with one, so a full stop after the URL is left out
_PROFILE_NAME = r"[\w%-](?:[\w.%-]*[\w%-])?/?"
# The look-behind stops a match on a domain that only ends like a platform, e.g. 'box.com' or 'mylinkedin.com'
_SOCIAL_PROFILE = rf"(?<![\w.@/-]){_SCHEME_AND_SUBDOMAIN}{_PLATFORMS}{_PROFILE_NAME}"


class SocialProfileRecognizer(PatternRecognizer):
    """Recognizes profile URLs on LinkedIn, Facebook, Instagram, X/Twitter, GitHub and TikTok. The whole URL is the match, with the scheme and subdomain if present.
    A platform without a profile (e.g. 'linkedin.com') and a LinkedIn company page are not matched."""

    def __init__(self):
        super().__init__(supported_entity=SOCIAL_PROFILE, patterns=[Pattern(name="social_profile", regex=_SOCIAL_PROFILE, score=PROFILE_SCORE)], supported_language=None)
