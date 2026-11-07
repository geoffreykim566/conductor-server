"""POST /v3/visit: the site's beacon, sent once per page view after the visitor engaged.
Bots are answered like anyone else and stored nowhere (README.md, Funnel)."""
import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, ValidationError

from app.core import channel, geo, visits
from app.core.config import VISIT_RATE_LIMIT
from app.core.ratelimit import client_ip, limiter

router = APIRouter()


class VisitIn(BaseModel):
    vid: uuid.UUID
    sid: uuid.UUID
    path: str = Field("/", max_length=200)
    utm_source: str | None = Field(None, max_length=100)
    utm_medium: str | None = Field(None, max_length=100)
    utm_campaign: str | None = Field(None, max_length=100)
    ref: str | None = Field(None, max_length=253)   # referrer host, outside the site
    webdriver: bool = False                          # navigator.webdriver: an automated browser


def _clean(s: str | None) -> str | None:
    return (s or "").strip().lower() or None


@router.post("/v3/visit", status_code=204)
@limiter.limit(VISIT_RATE_LIMIT)
async def visit(request: Request):
    # The page sends text/plain so the cross-origin POST needs no preflight: parse it ourselves.
    try:
        body = VisitIn.model_validate_json(await request.body())
    except ValidationError:
        return Response(status_code=204)
    ua = request.headers.get("user-agent")
    if body.webdriver or channel.is_bot(ua):
        return Response(status_code=204)
    utm, ref = _clean(body.utm_source), _clean(body.ref)
    await visits.insert(
        body.vid, body.sid, visits.normalize_path(body.path), channel.channel(utm or ref, ua),
        utm, _clean(body.utm_medium), _clean(body.utm_campaign), ref,
        geo.country(client_ip(request)), channel.device(ua),
    )
    return Response(status_code=204)
