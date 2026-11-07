"""Voice's local day, timezone handling and WAV duration."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core import stt, voice_usage

UTC = dt.timezone.utc


def test_local_day_and_next_midnight() -> None:
    now = dt.datetime(2026, 11, 7, 23, 30, tzinfo=UTC)       # 15:30 in LA, 08:30 next day in Tokyo
    assert voice_usage.local_day("America/Los_Angeles", now) == (
        dt.date(2026, 11, 7), dt.datetime(2026, 11, 8, 8, 0, tzinfo=UTC))
    assert voice_usage.local_day("Asia/Tokyo", now) == (
        dt.date(2026, 11, 8), dt.datetime(2026, 11, 8, 15, 0, tzinfo=UTC))


@pytest.mark.parametrize("name,ok", [("Europe/London", True), ("UTC", True), ("Mars/Olympus", False),
                                     ("", False), (None, False), ("../../etc/passwd", False)])
def test_valid_tz(name, ok) -> None:
    assert (voice_usage.valid_tz(name) is not None) == ok


def _pool():
    pool = SimpleNamespace(execute=AsyncMock())
    return patch.object(voice_usage.db, "pool", return_value=pool), pool


async def test_a_stored_timezone_wins_over_the_header() -> None:
    p, pool = _pool()
    with p:
        assert await voice_usage.user_timezone({"id": "u", "timezone": "Asia/Tokyo"}, "Europe/London") == "Asia/Tokyo"
    pool.execute.assert_not_awaited()


async def test_the_first_header_is_stored() -> None:
    p, pool = _pool()
    with p:
        assert await voice_usage.user_timezone({"id": "u", "timezone": None}, "Europe/London") == "Europe/London"
    pool.execute.assert_awaited_once()


async def test_no_timezone_falls_back_to_utc() -> None:
    p, pool = _pool()
    with p:
        assert await voice_usage.user_timezone({"id": "u", "timezone": None}, "nope") == "UTC"
    pool.execute.assert_not_awaited()


def test_left_never_negative() -> None:
    assert voice_usage.left(0) == 600 and voice_usage.left(650) == 0


def test_prompt_keeps_the_end_of_the_text() -> None:
    p = stt.prompt_for("x" * 2000 + " last words")
    assert p.endswith("last words") and len(p) == 900
