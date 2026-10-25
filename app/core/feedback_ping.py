"""Optional webhook ping for a new bug report or feedback (FEEDBACK_WEBHOOK_URL)."""
import logging
import uuid

import httpx

from app.core.config import ADMIN_BASE_URL, FEEDBACK_WEBHOOK_URL

log = logging.getLogger(__name__)


def ping_body(url: str, text: str) -> dict:
    """Discord reads `content`, Slack reads `text`."""
    return {"content": text} if "discord" in url else {"text": text}


async def send(feedback_id: uuid.UUID, kind: str, title: str, app_version: str | None) -> None:
    """Best effort: a failed ping is logged and never fails the report."""
    if not FEEDBACK_WEBHOOK_URL:
        return
    label = "Bug" if kind == "bug" else "Feedback"
    text = f"{label}: {title} (v{app_version or '?'})\n{ADMIN_BASE_URL}/admin#feedback/{feedback_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(FEEDBACK_WEBHOOK_URL, json=ping_body(FEEDBACK_WEBHOOK_URL, text))
            r.raise_for_status()
    except Exception as e:
        log.warning("[feedback_ping] failed: %r", e)
