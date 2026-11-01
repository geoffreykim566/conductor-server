"""SQL and actions behind the /admin Waitlist tab: the lists, bulk actions, invite sending, CSV."""
import asyncio
import csv
import io
import logging
import uuid
from zoneinfo import ZoneInfo

import httpx

from app.core import db, invite_mail

log = logging.getLogger(__name__)

# Resend's default limit is a few requests a second; stay well under it.
SEND_GAP_S = 0.6

_COLS = "id, email, created_at, source, approved_at, emailed_at, installs"


def _row(r) -> dict:
    iso = lambda t: t.isoformat() if t else None
    return {"id": str(r["id"]), "email": r["email"], "created_at": iso(r["created_at"]),
            "source": r["source"], "approved_at": iso(r["approved_at"]),
            "emailed_at": iso(r["emailed_at"]), "installs": r["installs"]}


async def waitlist_list(status: str) -> dict:
    approved = status == "approved"
    p = db.pool()
    rows = await p.fetch(f"""
        SELECT {_COLS} FROM waitlist
        WHERE approved_at IS {'NOT ' if approved else ''}NULL
        ORDER BY {'approved_at' if approved else 'created_at'} DESC
    """)
    counts = await p.fetchrow("""
        SELECT count(*) FILTER (WHERE approved_at IS NULL)::int      AS pending,
               count(*) FILTER (WHERE approved_at IS NOT NULL)::int  AS approved,
               count(*) FILTER (WHERE emailed_at IS NOT NULL)::int   AS emailed,
               count(*) FILTER (WHERE installs > 0)::int             AS installed
        FROM waitlist
    """)
    return {"rows": [_row(r) for r in rows], "counts": dict(counts),
            "email_configured": invite_mail.configured()}


_ACTIONS = {
    "approve":        "UPDATE waitlist SET approved_at = now() WHERE id = ANY($1) AND approved_at IS NULL",
    # Back on the waitlist; re-approving later emails them again.
    "unapprove":      "UPDATE waitlist SET approved_at = NULL, emailed_at = NULL WHERE id = ANY($1)",
    "reset_installs": "UPDATE waitlist SET installs = 0 WHERE id = ANY($1)",
    "delete":         "DELETE FROM waitlist WHERE id = ANY($1)",
}


async def apply(action: str, ids: list[uuid.UUID]) -> int:
    """Run one bulk action; returns the rows it changed."""
    result = await db.pool().execute(_ACTIONS[action], ids)
    return int(result.split()[-1])


async def to_email(ids: list[uuid.UUID], only_new: bool) -> list[tuple[uuid.UUID, str]]:
    """The approved rows among ids to send to (only_new: not emailed yet)."""
    rows = await db.pool().fetch(f"""
        SELECT id, email FROM waitlist
        WHERE id = ANY($1) AND approved_at IS NOT NULL {'AND emailed_at IS NULL' if only_new else ''}
    """, ids)
    return [(r["id"], r["email"]) for r in rows]


async def send_invites(targets: list[tuple[uuid.UUID, str]]) -> None:
    """Background task: one email per address; emailed_at is set only on success."""
    sent = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, (wid, email) in enumerate(targets):
            if i:
                await asyncio.sleep(SEND_GAP_S)
            if await invite_mail.send(client, email):
                await db.pool().execute("UPDATE waitlist SET emailed_at = now() WHERE id = $1", wid)
                sent += 1
    log.warning("[invite_mail] sent %d/%d", sent, len(targets))


_PT = ZoneInfo("America/Los_Angeles")


async def export_csv() -> str:
    """Every row; times in Pacific like the rest of admin."""
    rows = await db.pool().fetch(f"SELECT {_COLS} FROM waitlist ORDER BY created_at")
    pt = lambda t: t.astimezone(_PT).strftime("%Y-%m-%d %H:%M") if t else ""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "signed_up_pt", "source", "approved_pt", "emailed_pt", "macs"])
    for r in rows:
        w.writerow([r["email"], pt(r["created_at"]), r["source"] or "", pt(r["approved_at"]),
                    pt(r["emailed_at"]), r["installs"]])
    return out.getvalue()
