# api

The HTTP layer. `main.py` builds the FastAPI app (lifespan opens and closes the DB pool, then middleware, then the routers). Each resource is one router in `routes/`. `/docs` is disabled.

## Files

| File | What |
|---|---|
| `main.py` | The app: lifespan, middleware, routers. `uvicorn app.api.main:app` |
| `routes/chat.py` | `POST /v3/chat`: one turn, streamed as SSE |
| `routes/register.py` | `POST /v3/register`: mint a signed conductor id |
| `routes/me.py` | `GET/PUT/DELETE /v3/me`: free-message count, profile, uninstall marker |
| `routes/ratings.py` | `POST /v3/ratings`: thumbs on a reply's event |
| `routes/feedback.py` | `POST /v3/feedback`: a bug report or feedback from the client's Report Bug form |
| `schemas.py` | `ChatRequest` and its limits; the history shape whitelist |
| `history.py` | Trimming round-tripped history; spotting a parked research or plug-in-read turn |
| `middleware.py` | Body-size cap (before validation); 422 logging |
| `sse.py` | SSE framing |
| `deps.py` | `current_user`: verifies the `X-Conductor-Id` header (the only auth) |
| `admin/` | `/admin` KPI dashboard (basic auth): page, `/admin/stats`, `/admin/events`, `/admin/feedback` (+ `/{id}`, which marks it read). SQL in `queries.py`, `feedback_queries.py` |

## /v3/chat

**Request:**
- `message`
- `history`: exactly what the last `done` sent back
- `screenshots`: base64, this turn only
- `ax_state`: AX text, this turn only
- `research_confirm`
- `plugin_reads`: the client can read a plug-in (v0.4.2+), so Sol is offered `read_plugin_values`
- `resume`: `allow_research` | `deny_research` | `allow_plugin_read` | `deny_plugin_read`
- `plugin_values`: with `allow_plugin_read`, what the client read (`{plugin, track, values}` or `{error}`; shape and size checked in `schemas.py`)

**Events, in order:**
- `status` (zero or more)
- `chunk` (the reply text, as one chunk)
- then exactly one of:
  - `done`: `event_id`, `remaining`, `sources`, `walkthrough_steps`, `auto_run`, `history`
  - `research_prompt`: `query`, `history`
  - `plugin_read_prompt`: `plugin`, `track`, `history`
  - `error`: `kind` (`down` | `busy` | `retry`), `code` (the HTTP status behind it, or null) and `message`, the fixed text for the kind (Errors, below)

**Order of checks:**
1. The budget breaker returns 503.
2. A free message is claimed (402 at the limit), *before* any model call, failing closed.
3. A `resume` isn't charged again. It's checked for the matching parked call (`web_research` or `read_plugin_values`), else 422.

## Quirks & why

- **Conversation state lives in the client.** The client sends back the full raw history `respond()` produced (tool_use/tool_result included), and nothing is kept here. That's what makes multi-turn behaviour (backfill, fallbacks) work the same live as in the battery. `history.trim_history` cuts to `MAX_HISTORY_MESSAGES`, snapped to a real user turn so a `tool_result` is never orphaned.
- **The client is not a trust boundary.** History is replayed straight into the model call, so `schemas.py` whitelists exactly the shapes `pipeline/model_io.serialize_content` produces. A `tool_result.content` must be a string, because a block list could smuggle images or `cache_control`. Images and `cache_control` never appear in history (the pipeline keeps them on per-call copies).
- **Oversized screenshots are dropped, not rejected.** They're best-effort context the client sends silently. One oversized PNG (an old v0.3.0 client capturing a brushed-metal plugin skin) used to 422 every turn as "message too long".
- **422s are logged** (`[validation_422]`) with the failing field, and the response strips pydantic's input echo, which for screenshots is the whole image.
- **The body-size cap is middleware**, because uvicorn reads the body before pydantic runs. It's bounded by one turn's screenshots plus a text history; screenshots never accumulate.
- **No confidence badge:** `done` carries no tier (the client's badge was removed 10-21). The tier is a trace rule and fired on plain observations ("which tracks are muted"); it's still computed for the battery and the admin event log. Old clients read every `done` field with a default, so dropped fields (`source_tier`, and the locate-era `intent` / `locate_type` / `element` / `search_term`) are safe.
- **Known soft spot:** history isn't signed, so a hand-built "parked" transcript gets one uncharged answer. Accepted; the free tier is a soft cap.
- **Errors.** A failed turn tells the user only whether it's worth retrying; the cause stays in the log. `openai_io.post` retries 429 / 5xx / network / malformed tool JSON (4×, ~15 s), then raises `SolError(kind, cause)`:
  - `down` ("Conductor is down"): out of credit (`insufficient_quota`, not retried), a rejected key, 5xx or timeouts after retries.
  - `busy` ("Too many messages at once"): OpenAI's rate limit after retries. It's per org, so every user shares it.
  - `retry` ("Something went wrong… try again in a minute"): a 400 (we built a bad request) and any bug in our code.

  OpenAI isn't named and the credit state never leaks (user call, 10-18), but `code` is the native HTTP status (OpenAI's 401/429/5xx/400, or 500 for our bug; null for a timeout or a broken response) and the client shows it as `[Error 429]`, so a user's report still pins the cause (user call, 10-19). The client picks its own text from `kind`; `message` is there for older clients, which show it as is. Logged as `[sol_error] kind=… cause: HTTP …` (OpenAI's body included) or `[turn_error]` with the traceback. Without the traceback a missing migration once failed every lookup and nothing reached the logs.
- **A failed turn gives its free message back** (`db.refund_free_message`, never below 0), a resume included, since its charge was taken on the parked request. Silent: the client just refreshes the counter. A cancel (Esc, disconnect) is *not* refunded (user call, 10-18): the pipeline task is cancelled and the message stays used. Neither is a turn parked for research and never resumed.
- **Admin auth fails closed:** with no `ADMIN_PASSWORD`, nobody gets in.
- **Feedback** (`/v3/feedback`, migration 011): `kind` bug | feedback, `title` required, `message` optional, `context` the client's dump (chat, server transcript, recent AX dumps, last card, log tail, versions; always on a bug, opt-in on feedback, no screenshot by user call 10-24). Capped at 3 MB of context and `FEEDBACK_RATE_LIMIT` per IP. Each report pings `FEEDBACK_WEBHOOK_URL` when set (Discord gets `content`, anything else Slack's `text`; `app/core/feedback_ping.py`), linking to `/admin#feedback/<id>`. A failed ping is only logged (`[feedback_ping]`).

## Adding a route

Create `routes/<resource>.py` with `router = APIRouter()`, add it to the loop in `main.py`, and use `Depends(current_user)` for anything per-user. Rate-limited routes need a `request: Request` parameter for slowapi.
