"""POST /v3/feedback: a bug report or feedback from the client's Report Bug form."""
import json
from typing import Literal

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.core import db, feedback_ping
from app.core.config import FEEDBACK_RATE_LIMIT
from app.core.ratelimit import limiter

router = APIRouter()

# A whole session's chat and transcript plus a few AX dumps stays well under this.
MAX_CONTEXT_BYTES = 3 * 1024 * 1024


class FeedbackIn(BaseModel):
    kind: Literal["bug", "feedback"]
    title: str = Field(..., min_length=1, max_length=200)
    message: str | None = Field(None, max_length=10_000)
    app_version: str | None = Field(None, max_length=32)
    context: dict | None = None


@router.post("/v3/feedback")
@limiter.limit(FEEDBACK_RATE_LIMIT)
async def send_feedback(
    request: Request,
    f: FeedbackIn,
    background: BackgroundTasks,
    user: asyncpg.Record = Depends(current_user),
):
    title = f.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    if f.context is not None and len(json.dumps(f.context)) > MAX_CONTEXT_BYTES:
        raise HTTPException(status_code=413, detail="context_too_large")
    fid = await db.insert_feedback(
        user_id=user["id"], kind=f.kind, title=title,
        message=(f.message or "").strip() or None,
        app_version=f.app_version, context=f.context,
    )
    background.add_task(feedback_ping.send, fid, f.kind, title, f.app_version)
    return {"ok": True, "id": str(fid)}
