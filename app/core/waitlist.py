"""Waitlist queries outside admin: a signup, and claiming one install for a registering Mac."""
import re

from app.core import db

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normalize_email(raw: str | None) -> str | None:
    """Trimmed and lowercased, or None if it doesn't look like an address."""
    e = (raw or "").strip().lower()
    return e if len(e) <= 254 and _EMAIL.fullmatch(e) else None


async def join(email: str, source: str | None, channel: str, country: str | None) -> None:
    """Add a signup; signing up again changes nothing."""
    await db.pool().execute(
        """
        insert into waitlist (email, source, channel, country) values ($1, $2, $3, $4)
        on conflict (email) do nothing
        """,
        email, source, channel, country,
    )


async def claim_install(email: str, cap: int) -> str:
    """Take one install slot for a new Mac: 'ok', or why not ('not_on_waitlist',
    'not_approved', 'install_limit')."""
    p = db.pool()
    if await p.fetchval(
        """
        update waitlist set installs = installs + 1
        where email = $1 and approved_at is not null and installs < $2
        returning 1
        """,
        email, cap,
    ):
        return "ok"
    row = await p.fetchrow("select approved_at from waitlist where email = $1", email)
    if row is None:
        return "not_on_waitlist"
    return "not_approved" if row["approved_at"] is None else "install_limit"


async def release_install(email: str) -> None:
    """Give a slot back when the Mac turned out to be known after all (a concurrent register)."""
    await db.pool().execute(
        "update waitlist set installs = greatest(installs - 1, 0) where email = $1", email,
    )
