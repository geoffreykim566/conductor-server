"""POST /v3/waitlist: the landing page's signup form adds an email to the waitlist."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core import channel, geo, waitlist
from app.core.config import WAITLIST_RATE_LIMIT
from app.core.ratelimit import client_ip, limiter

router = APIRouter()


class JoinIn(BaseModel):
    email: str = Field(..., max_length=320)
    source: str | None = Field(None, max_length=100)
    # Honeypot: hidden on the page, so only a bot fills it in.
    company: str | None = Field(None, max_length=200)


@router.post("/v3/waitlist")
@limiter.limit(WAITLIST_RATE_LIMIT)
async def join_waitlist(request: Request, body: JoinIn):
    email = waitlist.normalize_email(body.email)
    if email is None:
        raise HTTPException(status_code=422, detail="invalid_email")
    if not body.company:
        source = (body.source or "").strip().lower() or None
        await waitlist.join(email, source,
                            channel.channel(source, request.headers.get("user-agent")),
                            geo.country(client_ip(request)))
    # Same answer for a new, repeat or bot signup: the page never shows who's on the list.
    return {"ok": True}
