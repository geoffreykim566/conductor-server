"""POST /v3/register: mint a signed conductor id, or return this Mac's existing one."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import device_hash
from app.core import db, signing
from app.core.config import REGISTER_RATE_LIMIT
from app.core.ratelimit import limiter

router = APIRouter()


@router.post("/v3/register")
@limiter.limit(REGISTER_RATE_LIMIT)
async def register(request: Request, device: str | None = Depends(device_hash)):
    new_id = uuid.uuid4()
    try:
        # Sign before inserting: without the secret, refuse rather than mint ids nothing can verify.
        token = signing.sign(new_id)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="registration_unavailable")
    cid = await db.register_user(new_id, device)
    return {"conductor_id": token if cid == new_id else signing.sign(cid)}
