"""/v3/me: the caller's free-message count, profile, and uninstall marker."""
import asyncpg
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.api.deps import current_user, device_hash
from app.core import db, voice_usage

router = APIRouter()


class Profile(BaseModel):
    experience: str | None = Field(None, max_length=50)
    role: str | None = Field(None, max_length=50)


@router.get("/v3/me")
async def get_me(user: asyncpg.Record = Depends(current_user),
                 device: str | None = Depends(device_hash),
                 x_conductor_timezone: str | None = Header(None)):
    if device and user["device_hash"] is None:
        await db.link_device(user["id"], device)
    tz = await voice_usage.user_timezone(user, x_conductor_timezone)
    day, resets_at = voice_usage.local_day(tz)
    return {
        "free_used": user["free_used"],
        "free_limit": user["free_limit"],
        "remaining": max(user["free_limit"] - user["free_used"], 0),
        # v0.4.5+: voice input's daily seconds (app/core/README.md, Voice)
        "voice_seconds_left": voice_usage.left(await voice_usage.used_seconds(user["id"], day)),
        "voice_resets_at": resets_at.isoformat(),
    }


@router.put("/v3/me")
async def update_me(p: Profile, user: asyncpg.Record = Depends(current_user)):
    await db.update_profile(user["id"], p.experience, p.role)
    return {"ok": True}


@router.delete("/v3/me")
async def delete_me(user: asyncpg.Record = Depends(current_user)):
    await db.mark_uninstalled(user["id"])
    return {"ok": True}
