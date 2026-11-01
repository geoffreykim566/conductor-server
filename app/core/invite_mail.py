"""The "you're in" email to an approved waitlist address, one recipient per send (Resend)."""
import logging

import httpx

from app.core import config

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
SUBJECT = "You're in: Conductor for Logic Pro"


def body_text(email: str) -> str:
    return (
        "You're off the waitlist. Thanks for waiting.\n\n"
        f"Download Conductor here: {config.DOWNLOAD_URL}\n\n"
        f"When the app opens, enter this email address ({email}) to get started. "
        f"It works on up to {config.WAITLIST_INSTALL_CAP} Macs.\n\n"
        "If anything goes wrong, just reply to this email.\n\n"
        "Conductor"
    )


def configured() -> bool:
    return bool(config.RESEND_API_KEY)


async def send(client: httpx.AsyncClient, email: str) -> bool:
    """True if Resend accepted it. A failure is logged, never raised."""
    try:
        r = await client.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            json={
                "from": config.INVITE_FROM,
                "to": [email],
                "reply_to": config.INVITE_REPLY_TO,
                "subject": SUBJECT,
                "text": body_text(email),
            },
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("[invite_mail] failed to=%s: %r", email, e)
        return False
