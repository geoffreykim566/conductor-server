"""/admin: the internal KPI dashboard page and the JSON endpoints it calls,
behind basic auth. Ported from v1 (README.md)."""
import secrets
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from app.api.admin import feedback_queries, funnel_queries, queries, waitlist_queries
from app.core import invite_mail
from app.core.config import ADMIN_PASSWORD, ADMIN_USER

router = APIRouter()
_security = HTTPBasic()
_HTML = Path(__file__).parent / "static" / "admin.html"


def _require_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    # Fail closed: with no password configured, nobody gets in.
    ok = bool(ADMIN_PASSWORD) and \
         secrets.compare_digest(credentials.username, ADMIN_USER) and \
         secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(_: None = Depends(_require_admin)):
    return HTMLResponse(_HTML.read_text())


@router.get("/admin/stats", include_in_schema=False)
async def stats(_: None = Depends(_require_admin)):
    return await queries.stats()


@router.get("/admin/funnel", include_in_schema=False)
async def funnel(_: None = Depends(_require_admin), days: int = 30):
    if days not in (7, 30, 90, 0):  # 0 = all time
        raise HTTPException(status_code=422, detail="days must be 7, 30, 90 or 0")
    return await funnel_queries.funnel(days or None)


@router.get("/admin/events", include_in_schema=False)
async def events_log(
    _: None = Depends(_require_admin),
    page: int = 1,
    limit: int = 50,
    user_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    event_type: str | None = None,
):
    return await queries.events_log(page, limit, user_id, from_date, to_date, event_type)


@router.get("/admin/feedback", include_in_schema=False)
async def feedback_list(
    _: None = Depends(_require_admin),
    page: int = 1,
    limit: int = 50,
    kind: str | None = None,
):
    return await feedback_queries.feedback_list(page, limit, kind)


@router.get("/admin/feedback/{fid}", include_in_schema=False)
async def feedback_detail(fid: uuid.UUID, _: None = Depends(_require_admin)):
    row = await feedback_queries.feedback_detail(fid)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    return row


@router.get("/admin/waitlist", include_in_schema=False)
async def waitlist_list(_: None = Depends(_require_admin),
                        status: Literal["pending", "approved"] = "pending"):
    return await waitlist_queries.waitlist_list(status)


class WaitlistAction(BaseModel):
    action: Literal["approve", "approve_email", "email", "unapprove", "reset_installs", "delete"]
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=1000)


@router.post("/admin/waitlist/action", include_in_schema=False)
async def waitlist_action(a: WaitlistAction, background: BackgroundTasks,
                          _: None = Depends(_require_admin)):
    sends = a.action in ("approve_email", "email")
    if sends and not invite_mail.configured():
        raise HTTPException(status_code=409, detail="email_not_configured")
    changed = await waitlist_queries.apply("approve" if sends else a.action, a.ids) \
        if a.action != "email" else 0
    targets = await waitlist_queries.to_email(a.ids, only_new=a.action == "approve_email") \
        if sends else []
    if targets:
        background.add_task(waitlist_queries.send_invites, targets)
    return {"changed": changed, "emailing": len(targets)}


@router.get("/admin/waitlist.csv", include_in_schema=False)
async def waitlist_csv(_: None = Depends(_require_admin)):
    return Response(await waitlist_queries.export_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=waitlist.csv"})
