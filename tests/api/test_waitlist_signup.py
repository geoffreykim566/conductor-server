"""/v3/waitlist: a valid email is stored normalized, a bot's honeypot isn't, a bad email is refused, CORS allows the site."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import waitlist
from app.core.ratelimit import limiter


@pytest.fixture
def wl():
    limiter.enabled = False
    with patch.object(waitlist.waitlist, "join", new=AsyncMock()) as join:
        yield TestClient(app), join
    limiter.enabled = True


def test_signup_is_stored_normalized(wl) -> None:
    c, join = wl
    r = c.post("/v3/waitlist", json={"email": " Sam@Example.com ", "source": " Instagram "})
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text
    join.assert_awaited_once_with("sam@example.com", "instagram")


def test_signup_without_source(wl) -> None:
    c, join = wl
    assert c.post("/v3/waitlist", json={"email": "a@b.co", "source": ""}).status_code == 200
    join.assert_awaited_once_with("a@b.co", None)


def test_honeypot_answers_ok_but_stores_nothing(wl) -> None:
    c, join = wl
    r = c.post("/v3/waitlist", json={"email": "a@b.co", "company": "Spam Inc"})
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text
    join.assert_not_awaited()


@pytest.mark.parametrize("email", ["", "nope", "a@b", "a b@c.co", "@b.co", "a@@b.co", "x" * 250 + "@b.co"])
def test_bad_email_is_refused(wl, email) -> None:
    c, join = wl
    assert c.post("/v3/waitlist", json={"email": email}).status_code == 422
    join.assert_not_awaited()


def test_cors_allows_the_site_only(wl) -> None:
    c, _ = wl
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = c.options("/v3/waitlist", headers={"Origin": "https://askconductor.ai", **pre})
    assert ok.headers.get("access-control-allow-origin") == "https://askconductor.ai", ok.headers
    bad = c.options("/v3/waitlist", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in bad.headers, bad.headers
