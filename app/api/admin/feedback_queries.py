"""SQL behind the /admin Feedback tab: the paged list and one report with its context."""
import uuid

from app.core import db


async def feedback_list(page: int, limit: int, kind: str | None) -> dict:
    p = db.pool()
    limit = max(1, min(limit, 200))
    offset = (max(1, page) - 1) * limit
    where, params = ("WHERE kind = $1", [kind]) if kind else ("", [])

    total = await p.fetchval(f"SELECT count(*)::int FROM feedback {where}", *params)
    unread = await p.fetchval("SELECT count(*)::int FROM feedback WHERE read_at IS NULL")
    params.extend([limit, offset])
    rows = await p.fetch(f"""
        SELECT id, created_at, user_id, kind, title, message, app_version,
               context IS NOT NULL AS has_context, read_at IS NOT NULL AS is_read
        FROM feedback
        {where}
        ORDER BY created_at DESC
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
    """, *params)

    return {
        "rows": [{
            "id":          str(r["id"]),
            "created_at":  r["created_at"].isoformat(),
            "user_id":     str(r["user_id"]),
            "kind":        r["kind"],
            "title":       r["title"],
            "message":     r["message"],
            "app_version": r["app_version"],
            "has_context": r["has_context"],
            "is_read":     r["is_read"],
        } for r in rows],
        "total":  total,
        "unread": unread,
        "page":   page,
        "pages":  max(1, (total + limit - 1) // limit),
    }


async def feedback_detail(fid: uuid.UUID) -> dict | None:
    """One report with its context; opening it marks it read."""
    r = await db.pool().fetchrow("""
        UPDATE feedback SET read_at = coalesce(read_at, now())
        WHERE id = $1
        RETURNING id, created_at, user_id, kind, title, message, app_version, context
    """, fid)
    if r is None:
        return None
    return {
        "id":          str(r["id"]),
        "created_at":  r["created_at"].isoformat(),
        "user_id":     str(r["user_id"]),
        "kind":        r["kind"],
        "title":       r["title"],
        "message":     r["message"],
        "app_version": r["app_version"],
        "context":     r["context"],
    }
