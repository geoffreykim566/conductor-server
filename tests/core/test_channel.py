"""Channel normalising (utm tag, referrer host, in-app user agent) and bot detection."""
from __future__ import annotations

import pytest

from app.core import channel

SAFARI = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"


@pytest.mark.parametrize("label,want", [
    ("ig", "instagram"), ("Instagram", "instagram"), ("tt", "tiktok"), ("yt", "youtube"),
    ("twitter", "x"), ("l.instagram.com", "instagram"), ("www.youtube.com", "youtube"),
    ("m.youtube.com", "youtube"), ("t.co", "x"), ("out.reddit.com", "reddit"),
    ("www.google.co.uk", "search"), ("gemini.google.com", "ai"), ("chatgpt.com", "ai"),
    ("logicprohelp.com", "logicprohelp.com"), ("podcast", "podcast"),
])
def test_label_maps_to_channel(label, want) -> None:
    assert channel.channel(label, SAFARI) == want, channel.channel(label, SAFARI)


@pytest.mark.parametrize("suffix,want", [
    (" Instagram 350.0.0.0", "instagram"), (" [FBAN/FBIOS;FBAV/480.0]", "facebook"),
    (" musical_ly_37.0 BytedanceWebview/d8a21c6", "tiktok"), (" LinkedInApp", "linkedin"),
    (" Barcelona 350.0", "threads"), ("", "direct"),
])
def test_in_app_browser_without_referrer(suffix, want) -> None:
    assert channel.channel(None, IPHONE + suffix) == want


def test_utm_beats_the_user_agent() -> None:
    assert channel.channel("yt", IPHONE + " Instagram 350.0") == "youtube"


def test_host_suffix_needs_a_dot_boundary() -> None:
    assert channel.channel("notx.com", SAFARI) == "notx.com"


@pytest.mark.parametrize("ua", [
    None, "", "Googlebot/2.1", "Mozilla/5.0 (compatible; bingbot/2.0)", "facebookexternalhit/1.1",
    "Mozilla/5.0 HeadlessChrome/131.0", "curl/8.4", "python-httpx/0.27", "Twitterbot/1.0",
    "Mozilla/5.0 (compatible; Discordbot/2.0)", "Slackbot-LinkExpanding 1.0",
])
def test_bots_are_detected(ua) -> None:
    assert channel.is_bot(ua)


@pytest.mark.parametrize("ua", [SAFARI, IPHONE + " Instagram 350.0"])
def test_browsers_are_not_bots(ua) -> None:
    assert not channel.is_bot(ua)


def test_device() -> None:
    assert (channel.device(SAFARI), channel.device(IPHONE), channel.device("Mozilla/5.0 (iPad; CPU OS 18_0)")) \
        == ("desktop", "mobile", "tablet")
