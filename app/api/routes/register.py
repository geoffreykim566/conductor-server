"""POST /v3/register: mint a signed conductor id, or return this Mac's existing one.
A new Mac needs an approved waitlist email (README.md, Waitlist)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import device_hash
from app.core import config, db, signing, waitlist
from app.core.config import REGISTER_RATE_LIMIT
from app.core.ratelimit import limiter

router = APIRouter()


class RegisterIn(BaseModel):
    email: str | None = Field(None, max_length=320)


@router.post("/v3/register")
@limiter.limit(REGISTER_RATE_LIMIT)
async def register(request: Request, body: RegisterIn | None = None,
                   device: str | None = Depends(device_hash)):
    new_id = uuid.uuid4()
    try:
        # Sign before inserting: without the secret, refuse rather than mint ids nothing can verify.
        token = signing.sign(new_id)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="registration_unavailable")

    email = None
    if config.WAITLIST_REQUIRED and not (device and await db.known_device(device)):
        email = waitlist.normalize_email(body.email if body else None)
        if email is None:
            raise HTTPException(status_code=403, detail="email_required")
        status = await waitlist.claim_install(email, config.WAITLIST_INSTALL_CAP)
        if status != "ok":
            raise HTTPException(status_code=403, detail=status)

    cid = await db.register_user(new_id, device)
    if email and cid != new_id:
        await waitlist.release_install(email)  # another register for this Mac won the race
    return {"conductor_id": token if cid == new_id else signing.sign(cid)}
