"""/v3/transcribe: duration from the WAV header, the daily limit claimed before OpenAI, a refund on failure."""
from __future__ import annotations

import base64
import datetime as dt
import io
import wave
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.api.main import app
from app.api.routes import transcribe as route
from app.core import stt
from app.core.ratelimit import limiter

USER = {"id": "u1", "timezone": "Europe/London"}
DAY = dt.date(2026, 11, 7)
RESETS = dt.datetime(2026, 11, 8, 0, 0, tzinfo=dt.timezone.utc)


def wav(seconds: float, rate: int = 16000) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(seconds * rate))
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def api():
    limiter.enabled = False
    app.dependency_overrides[current_user] = lambda: USER
    mocks = {
        "user_timezone": AsyncMock(return_value="Europe/London"),
        "claim": AsyncMock(return_value=130.0),
        "refund": AsyncMock(),
        "record_billed": AsyncMock(),
    }
    with patch.object(route.voice_usage, "local_day", return_value=(DAY, RESETS)), \
            patch.object(route.budget, "over_daily_budget", new=AsyncMock(return_value=False)), \
            patch.multiple(route.voice_usage, **mocks), \
            patch.object(route.stt, "transcribe", new=AsyncMock(return_value=("Open ChromaVerb", 3.0))) as tr:
        yield TestClient(app), mocks, tr
    app.dependency_overrides.clear()
    limiter.enabled = True


def _post(c, audio: str, **extra):
    return c.post("/v3/transcribe", json={"audio": audio, "context": "so far", **extra},
                  headers={"X-Conductor-Id": "x", "X-Conductor-Timezone": "Europe/London"})


def test_a_phrase_is_transcribed_and_counted(api) -> None:
    c, m, tr = api
    r = _post(c, wav(2.5))
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "Open ChromaVerb", "seconds_left": 470, "resets_at": RESETS.isoformat()}
    m["claim"].assert_awaited_once_with("u1", DAY, 2.5)
    assert tr.await_args.args[1] == "so far"
    m["record_billed"].assert_awaited_once_with("u1", DAY, 3.0)


def test_at_the_limit_openai_is_not_called(api) -> None:
    c, m, tr = api
    m["claim"].return_value = None
    r = _post(c, wav(2))
    assert r.status_code == 402
    assert r.json() == {"detail": "voice_limit", "seconds_left": 0, "resets_at": RESETS.isoformat()}
    tr.assert_not_awaited()


def test_a_failed_call_gives_the_seconds_back(api) -> None:
    c, m, tr = api
    tr.side_effect = stt.SttError("busy", 429, "rate limited")
    r = _post(c, wav(2))
    assert r.status_code == 502
    assert r.json()["kind"] == "busy" and r.json()["code"] == 429
    m["refund"].assert_awaited_once_with("u1", DAY, 2.0)
    m["record_billed"].assert_not_awaited()


@pytest.mark.parametrize("audio", ["not base64!!", base64.b64encode(b"RIFFjunk").decode(), wav(0)])
def test_bad_audio_is_refused_before_anything_is_claimed(api, audio) -> None:
    c, m, tr = api
    assert _post(c, audio).status_code == 422
    m["claim"].assert_not_awaited()


def test_a_clip_over_the_cap_is_refused(api) -> None:
    c, m, _ = api
    assert _post(c, wav(63)).status_code == 422
    m["claim"].assert_not_awaited()


def test_over_budget_is_a_503(api) -> None:
    c, m, tr = api
    with patch.object(route.budget, "over_daily_budget", new=AsyncMock(return_value=True)):
        assert _post(c, wav(2)).status_code == 503
    m["claim"].assert_not_awaited()
