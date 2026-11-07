"""POST /v3/transcribe: one spoken phrase (16-bit PCM WAV, base64) to text, within the
caller's daily voice seconds. Order of checks and why: app/api/README.md (Voice)."""
import base64
import binascii
import logging

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.core import budget, stt, voice_usage
from app.core.config import TRANSCRIBE_RATE_LIMIT, VOICE_MAX_CLIP_SECONDS
from app.core.ratelimit import limiter

log = logging.getLogger(__name__)
router = APIRouter()


class TranscribeRequest(BaseModel):
    audio: str = Field(..., max_length=4_000_000)   # base64 of <= ~62 s at 16 kHz mono
    context: str = Field("", max_length=4000)       # the text already in the box


def _limit_body(resets_at) -> dict:
    return {"detail": "voice_limit", "seconds_left": 0, "resets_at": resets_at.isoformat()}


@router.post("/v3/transcribe")
@limiter.limit(TRANSCRIBE_RATE_LIMIT)
async def transcribe(request: Request, body: TranscribeRequest,
                     user: asyncpg.Record = Depends(current_user),
                     x_conductor_timezone: str | None = Header(None)):
    try:
        audio = base64.b64decode(body.audio, validate=True)
        seconds = stt.wav_seconds(audio)
    except (binascii.Error, stt.BadAudio) as e:
        raise HTTPException(status_code=422, detail=f"bad_audio: {e}")
    if seconds > VOICE_MAX_CLIP_SECONDS:
        raise HTTPException(status_code=422, detail="clip_too_long")
    if await budget.over_daily_budget():
        return JSONResponse({"detail": "over_budget", "kind": "down"}, status_code=503)

    tz = await voice_usage.user_timezone(user, x_conductor_timezone)
    day, resets_at = voice_usage.local_day(tz)
    total = await voice_usage.claim(user["id"], day, seconds)
    if total is None:
        return JSONResponse(_limit_body(resets_at), status_code=402)

    try:
        text, billed = await stt.transcribe(audio, body.context)
    except stt.SttError as e:
        await voice_usage.refund(user["id"], day, seconds)
        log.warning("[stt_error] kind=%s %s", e.kind, e)
        return JSONResponse({"detail": "stt_failed", "kind": e.kind, "code": e.status}, status_code=502)
    await voice_usage.record_billed(user["id"], day, billed if billed is not None else seconds)
    return {"text": text, "seconds_left": voice_usage.left(total), "resets_at": resets_at.isoformat()}
