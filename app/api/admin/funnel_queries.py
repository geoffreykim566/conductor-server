"""SQL behind the admin Funnel tab: visits → signups → invites → installs → use, by day,
channel and country. Every stage counts what happened in the period (not a cohort)."""
from collections import defaultdict

from app.core import channel, db

_PT = "America/Los_Angeles"


def _since(days: int | None) -> str:
    return "now() - make_interval(days => $1)" if days else "'-infinity'::timestamptz"


def _args(days: int | None) -> list:
    return [days] if days else []


def _ch(raw: str | None, unknown: str) -> str:
    """Stored channels, and pre-015 raw sources, through the same normaliser."""
    return channel.channel(raw, None) if raw else unknown


async def funnel(days: int | None) -> dict:
    p = db.pool()
    since, a = _since(days), _args(days)

    totals = dict(await p.fetchrow(f"""
        WITH v AS (SELECT * FROM visits WHERE created_at >= {since}),
             first_seen AS (SELECT visitor_id, min(created_at) AS at FROM visits GROUP BY 1),
             u AS (SELECT id FROM users WHERE created_at >= {since}),
             days_used AS (
                SELECT e.user_id, count(DISTINCT (e.created_at AT TIME ZONE '{_PT}')::date) AS n
                FROM events e JOIN u ON u.id = e.user_id GROUP BY 1)
        SELECT
            (SELECT count(DISTINCT session_id) FROM v)::int                                AS visits,
            (SELECT count(*) FROM v)::int                                                  AS page_views,
            (SELECT count(DISTINCT visitor_id) FROM v)::int                                AS visitors,
            (SELECT count(*) FROM first_seen WHERE at >= {since})::int                     AS new_visitors,
            (SELECT count(*) FROM first_seen)::int                                         AS visitors_ever,
            (SELECT count(DISTINCT visitor_id) FROM v WHERE path = '/download')::int       AS download_visitors,
            (SELECT count(*) FROM waitlist WHERE created_at  >= {since})::int              AS signups,
            (SELECT count(*) FROM waitlist WHERE approved_at >= {since})::int              AS approved,
            (SELECT count(*) FROM waitlist WHERE emailed_at  >= {since})::int              AS invited,
            (SELECT count(*) FROM u)::int                                                  AS installs,
            (SELECT count(*) FROM days_used)::int                                          AS activated,
            (SELECT count(*) FROM days_used WHERE n >= 2)::int                             AS returned
    """, *a))

    daily = [dict(r) for r in await p.fetch(f"""
        WITH d AS (
            SELECT (created_at AT TIME ZONE '{_PT}')::date AS day, session_id, visitor_id
            FROM visits WHERE created_at >= {since}),
             first_seen AS (
            SELECT (min(created_at) AT TIME ZONE '{_PT}')::date AS day FROM visits GROUP BY visitor_id),
             days AS (
            SELECT day FROM d UNION
            SELECT (created_at AT TIME ZONE '{_PT}')::date FROM waitlist WHERE created_at >= {since} UNION
            SELECT (created_at AT TIME ZONE '{_PT}')::date FROM users    WHERE created_at >= {since})
        SELECT days.day::text AS day,
            (SELECT count(DISTINCT session_id) FROM d WHERE d.day = days.day)::int  AS visits,
            (SELECT count(DISTINCT visitor_id) FROM d WHERE d.day = days.day)::int  AS visitors,
            (SELECT count(*) FROM first_seen f WHERE f.day = days.day)::int        AS new_visitors,
            (SELECT count(*) FROM waitlist w
              WHERE (w.created_at AT TIME ZONE '{_PT}')::date = days.day)::int     AS signups,
            (SELECT count(*) FROM users x
              WHERE (x.created_at AT TIME ZONE '{_PT}')::date = days.day)::int     AS installs
        FROM days ORDER BY days.day
    """, *a)]

    # A visit's channel is its session's first page view; a new visitor's is their first visit's.
    visit_rows = await p.fetch(f"""
        WITH s AS (
            SELECT DISTINCT ON (session_id) session_id, channel, country
            FROM visits WHERE created_at >= {since} ORDER BY session_id, created_at),
             f AS (
            SELECT DISTINCT ON (visitor_id) visitor_id, created_at, channel, country
            FROM visits ORDER BY visitor_id, created_at)
        SELECT 'visits' AS k, channel, country, count(*)::int AS n FROM s GROUP BY 2, 3
        UNION ALL
        SELECT 'new_visitors', channel, country, count(*)::int FROM f WHERE created_at >= {since} GROUP BY 2, 3
    """, *a)
    signup_rows = await p.fetch(f"""
        SELECT coalesce(channel, source) AS channel, country, count(*)::int AS n
        FROM waitlist WHERE created_at >= {since} GROUP BY 1, 2
    """, *a)
    user_rows = await p.fetch(f"""
        WITH u AS (SELECT id, channel, country FROM users WHERE created_at >= {since}),
             days_used AS (
                SELECT e.user_id, count(DISTINCT (e.created_at AT TIME ZONE '{_PT}')::date) AS n
                FROM events e JOIN u ON u.id = e.user_id GROUP BY 1)
        SELECT u.channel, u.country, count(*)::int AS installs,
               count(d.user_id)::int AS activated,
               count(*) FILTER (WHERE d.n >= 2)::int AS returned
        FROM u LEFT JOIN days_used d ON d.user_id = u.id GROUP BY 1, 2
    """, *a)

    by = {"channel": defaultdict(lambda: defaultdict(int)), "country": defaultdict(lambda: defaultdict(int))}

    def add(ch: str, country: str | None, key: str, n: int) -> None:
        by["channel"][ch][key] += n
        by["country"][country or "unknown"][key] += n

    for r in visit_rows:
        add(r["channel"], r["country"], r["k"], r["n"])
    for r in signup_rows:
        # A pre-015 signup with no source had no referrer: direct.
        add(_ch(r["channel"], "direct"), r["country"], "signups", r["n"])
    for r in user_rows:
        # A user with no channel registered before tracking, or with no waitlist email.
        ch = _ch(r["channel"], "unknown")
        for key in ("installs", "activated", "returned"):
            add(ch, r["country"], key, r[key])

    def table(kind: str) -> list[dict]:
        rows = [{"label": k, **v} for k, v in by[kind].items()]
        return sorted(rows, key=lambda r: (-r.get("visits", 0), -r.get("signups", 0), -r.get("installs", 0)))

    return {"days": days, "totals": totals, "daily": daily,
            "by_channel": table("channel"), "by_country": table("country")}
