"""Identity — the only place auth is decided.

X-Conductor-Id carries a server-signed token (`<uuid>.<sig>`, minted by
/v3/register — see signing.py). A bare or tampered uuid fails HMAC
verification before ever touching the DB; a valid token is upserted lazily
so a row lost to a DB reset self-heals.
"""
import re

import asyncpg
from fastapi import Header, HTTPException

from app.core import db, signing

_HEX64 = re.compile(r"[0-9a-f]{64}")


async def current_user(x_conductor_id: str = Header(...)) -> asyncpg.Record:
    cid = signing.verify(x_conductor_id)
    if cid is None:
        raise HTTPException(status_code=401, detail="invalid_conductor_id")
    return await db.get_or_create_user(cid)


def device_hash(x_conductor_device: str | None = Header(None)) -> str | None:
    """The client's SHA-256 of its Mac's hardware UUID, or None if missing or malformed."""
    h = (x_conductor_device or "").strip().lower()
    return h if _HEX64.fullmatch(h) else None
