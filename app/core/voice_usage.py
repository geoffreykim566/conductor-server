"""Voice input's daily limit: seconds per user per local day, claimed before the OpenAI call.
Why local days, the claim-first order and the stored timezone: README.md (Voice)."""
import datetime as dt
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core import db
from app.core.config import VOICE_DAILY_SECONDS

FALLBACK_TZ = "UTC"


def valid_tz(name: str | None) -> str | None:
    name = (name or "").strip()
    if not name or len(name) > 64:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


async def user_timezone(user, header_tz: str | None) -> str:
    """The stored timezone; else the header's, stored now (first one wins); else UTC."""
    stored = valid_tz(user.get("timezone"))
    if stored:
        return stored
    sent = valid_tz(header_tz)
    if sent:
        await db.pool().execute(
            "update users set timezone = $2 where id = $1 and timezone is null", user["id"], sent)
        return sent
    return FALLBACK_TZ


def local_day(tz: str, now: dt.datetime | None = None) -> tuple[dt.date, dt.datetime]:
    """(today in `tz`, the next local midnight as an aware UTC datetime)."""
    zone = ZoneInfo(tz)
    local = (now or dt.datetime.now(dt.timezone.utc)).astimezone(zone)
    midnight = dt.datetime.combine(local.date() + dt.timedelta(days=1), dt.time(), tzinfo=zone)
    return local.date(), midnight.astimezone(dt.timezone.utc)


async def used_seconds(user_id: uuid.UUID, day: dt.date) -> float:
    v = await db.pool().fetchval(
        "select seconds from voice_usage where user_id = $1 and day = $2", user_id, day)
    return float(v or 0)


async def claim(user_id: uuid.UUID, day: dt.date, seconds: float) -> float | None:
    """Add `seconds` to today's count while it's under the limit; the new total, or None at the
    limit. A clip that starts under the limit is let through whole (at most one clip over)."""
    total = await db.pool().fetchval(
        """
        insert into voice_usage as v (user_id, day, seconds, clips)
        values ($1, $2, $3, 1)
        on conflict (user_id, day) do update
            set seconds = v.seconds + excluded.seconds, clips = v.clips + 1, updated_at = now()
            where v.seconds < $4
        returning seconds
        """,
        user_id, day, seconds, VOICE_DAILY_SECONDS,
    )
    return float(total) if total is not None else None


async def refund(user_id: uuid.UUID, day: dt.date, seconds: float) -> None:
    """Give back a clip whose transcription failed."""
    await db.pool().execute(
        """
        update voice_usage set seconds = greatest(seconds - $3, 0), clips = greatest(clips - 1, 0)
        where user_id = $1 and day = $2
        """,
        user_id, day, seconds,
    )


async def record_billed(user_id: uuid.UUID, day: dt.date, billed: float) -> None:
    await db.pool().execute(
        "update voice_usage set billed_seconds = billed_seconds + $3 where user_id = $1 and day = $2",
        user_id, day, billed,
    )


def left(used: float) -> int:
    return max(int(VOICE_DAILY_SECONDS - used), 0)
