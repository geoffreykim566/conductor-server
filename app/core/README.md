# core

Shared infrastructure that every other package imports. Nothing in here imports from `api/`, `pipeline/` or `tools/`.

## Files

| File | What |
|---|---|
| `config.py` | Every setting: env vars plus model names. Secrets only from env (`.env.local` locally) |
| `db.py` | asyncpg pool (jsonb codec) and every query outside admin |
| `signing.py` | HMAC-signed conductor ids (`<uuid>.<sig>`) |
| `ratelimit.py` | slowapi limiter keyed by client IP |
| `budget.py` | Daily-spend circuit breaker |
| `feedback_ping.py` | Optional webhook ping per bug report / feedback (`FEEDBACK_WEBHOOK_URL`) |
| `waitlist.py` | Waitlist queries outside admin: email normalizing, signup, claiming an install slot at register |
| `channel.py` | A visit's or signup's channel (utm tag, in-app user agent, referrer host) and bot detection |
| `geo.py` | Country of an IP from the local DB-IP Lite file; the IP is never stored |
| `visits.py` | Storing one counted page view from the site's beacon |
| `invite_mail.py` | The invite email, one recipient per send through Resend (`RESEND_API_KEY`) |

## Quirks & why

- **Models:**
  - `SOL_MODEL` is the only decider: GPT-6.1 Sol on OpenAI's Responses API, needs `OPENAI_API_KEY` (why, and why there's no fallback model: `pipeline/README.md`, Sol decider). `SOL_MAX_OUTPUT_TOKENS` is 8192 because Responses counts reasoning as output.
  - Research runs on Sol too, at `RESEARCH_EFFORT` low (`research/README.md`). No Anthropic key or package is used anywhere.
  - Changing the decider model needs a battery run first.
  - Haiku as decider was rejected: it missed cards, and its prompt fell under Haiku's 4096-token cache minimum, so it cost more per turn.
- **`RESEARCH_CALL_TIMEOUT_S` = 90s.** Sol research took median 35 s, max 71 s over 40 calls (10-19, `test_runs/2026-10-19/research_latency*`). It must stay under the client's 120 s read timeout, or a slow call ends in the client's canned timeout reply while the server is still working. (150 s was the Claude-era ceiling.)
- **Signing:** only `/v3/register` signs. A forged or bare uuid fails verification before touching the DB, and a valid token whose row was lost (DB reset) is upserted lazily (`api/deps.py`). No secret configured = registration returns 503 and every verify fails, closed.
- **Budget:** the console spend cap on the central key is the hard backstop, but tripping it takes the whole beta down until it resets. This breaker trips first, on trailing-24h `event_costs` > `DAILY_BUDGET_USD`, and recovers on its own. `event_costs` (migration 009) prices Sol events at $2 in / $0.10 cached / $10 out per M (OpenAI standard tier, 10-19) and older `claude-*` rows at 004's $3/$15. `tokens_in` is uncached input only; cached input is `tokens_cached`. Web-search fees aren't counted, so research turns run slightly under. It's cached for 60s, so one aggregate query per minute.
- **Rate limit:** IPv6 is keyed per /64, because privacy extensions mint a fresh address per connection. A malformed IP is used as-is rather than raising.
- **`FREE_LIMIT`** (100 since 10-30) is the default for new users. It's copied into each `users` row at register, so changing it for existing users takes a migration (013). Raising one local user's count in dev: the `grant-free-messages` skill.
- **Country database:** DB-IP Lite country (CC BY 4.0: the admin Funnel tab and the privacy page credit it), fetched at image build by `docker/fetch_geo.py` into `/opt/geo` (outside `/srv`, so the standalone stack's bind mount doesn't hide it). Their CDN 403s Python's default user agent, so the script sends its own. A failed download doesn't fail the build: countries are just unknown, logged once as `[geo]`. It's only as fresh as that build layer: a cached layer keeps the old month's file (countries barely move, so fine).
