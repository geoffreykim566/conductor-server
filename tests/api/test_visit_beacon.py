"""/v3/visit: a real browser's view is stored with its channel; bots, automation and junk are dropped silently."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import visit
from app.core import visits
from app.core.ratelimit import limiter

SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15"
VID, SID = str(uuid.uuid4()), str(uuid.uuid4())


@pytest.fixture
def beacon():
    limiter.enabled = False
    with patch.object(visit.visits, "insert", new=AsyncMock()) as ins, \
            patch.object(visit.geo, "country", return_value="US"):
        yield TestClient(app), ins
    limiter.enabled = True


def _post(c, body: dict, ua: str = SAFARI):
    # The page sends text/plain (no CORS preflight), so the route parses the raw body.
    return c.post("/v3/visit", content=json.dumps(body),
                  headers={"Content-Type": "text/plain", "User-Agent": ua})


def test_a_browser_view_is_stored(beacon) -> None:
    c, ins = beacon
    r = _post(c, {"vid": VID, "sid": SID, "path": "/index.html", "utm_source": " IG ", "ref": "l.instagram.com"})
    assert r.status_code == 204, r.text
    args = ins.await_args.args
    assert (str(args[0]), str(args[1]), args[2], args[3], args[4]) == (VID, SID, "/", "instagram", "ig"), args
    assert (args[7], args[8], args[9]) == ("l.instagram.com", "US", "desktop"), args


@pytest.mark.parametrize("ua", ["Googlebot/2.1", "Mozilla/5.0 HeadlessChrome/131.0", ""])
def test_bots_are_dropped(beacon, ua) -> None:
    c, ins = beacon
    assert _post(c, {"vid": VID, "sid": SID}, ua=ua).status_code == 204
    ins.assert_not_awaited()


def test_automated_browser_is_dropped(beacon) -> None:
    c, ins = beacon
    assert _post(c, {"vid": VID, "sid": SID, "webdriver": True}).status_code == 204
    ins.assert_not_awaited()


@pytest.mark.parametrize("raw", ["", "not json", json.dumps({"vid": "nope", "sid": SID}), json.dumps({"sid": SID})])
def test_junk_is_dropped(beacon, raw) -> None:
    c, ins = beacon
    r = c.post("/v3/visit", content=raw, headers={"Content-Type": "text/plain", "User-Agent": SAFARI})
    assert r.status_code == 204, r.text
    ins.assert_not_awaited()


@pytest.mark.parametrize("raw,want", [
    ("/", "/"), ("/index.html", "/"), ("/download", "/download"), ("/download.html", "/download"),
    ("/download/", "/download"), ("/privacy?x=1", "/privacy"), ("/wp-admin", "other"), ("", "/"),
])
def test_paths_are_normalised(raw, want) -> None:
    assert visits.normalize_path(raw) == want
