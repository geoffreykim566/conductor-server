"""Storing one counted page view from the site's visit beacon."""
import uuid

from app.core import db

PATHS = {"/": "/", "/index": "/", "/download": "/download", "/privacy": "/privacy"}


def normalize_path(raw: str) -> str:
    """'/download.html' and '/download/' → '/download'; anything unknown → 'other'."""
    p = (raw or "/").split("?")[0].split("#")[0].strip().lower()
    p = p.removesuffix(".html").rstrip("/") or "/"
    return PATHS.get(p, "other")


async def insert(visitor_id: uuid.UUID, session_id: uuid.UUID, path: str, channel: str,
                 utm_source: str | None, utm_medium: str | None, utm_campaign: str | None,
                 referrer_host: str | None, country: str | None, device: str) -> None:
    await db.pool().execute(
        """
        insert into visits (visitor_id, session_id, path, channel, utm_source, utm_medium,
                            utm_campaign, referrer_host, country, device)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        visitor_id, session_id, path, channel, utm_source, utm_medium, utm_campaign,
        referrer_host, country, device,
    )
