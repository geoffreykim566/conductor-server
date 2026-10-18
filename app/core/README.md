# core

Shared infrastructure that every other package imports. Nothing in here imports from `api/`, `pipeline/` or `tools/`.

## Files

| File | What |
|---|---|
| `config.py` | Every setting: env vars plus model names. Secrets only from env (`.env.local` locally) |
| `db.py` | asyncpg pool (pgvector + jsonb codecs) and every query outside admin |
| `signing.py` | HMAC-signed conductor ids (`<uuid>.<sig>`) |
| `ratelimit.py` | slowapi limiter keyed by client IP |
| `budget.py` | Daily-spend circuit breaker |

## Quirks & why

- **Models:**
  - `SOL_MODEL` is the only decider: GPT-6.1 Sol on OpenAI's Responses API, needs `OPENAI_API_KEY` (why, and why there's no fallback model: `pipeline/README.md`, Sol decider). `SOL_MAX_OUTPUT_TOKENS` is 8192 because Responses counts reasoning as output.
  - `RESEARCH_MODEL` is still Claude (Sonnet 5.5, on `CENTRAL_ANTHROPIC_KEY`) until `web_research` is ported to OpenAI: on Sonnet 5 half the battery's research calls hit the 150 s timeout.
  - Changing the decider model needs a battery run first.
  - Haiku as decider was rejected: it missed cards, and its prompt fell under Haiku's 4096-token cache minimum, so it cost more per turn.
- **`RESEARCH_CALL_TIMEOUT_S` = 150s.** 90s timed out every real research call, and a timed-out call can never earn the "research" tier.
- **Signing:** only `/v3/register` signs. A forged or bare uuid fails verification before touching the DB, and a valid token whose row was lost (DB reset) is upserted lazily (`api/deps.py`). No secret configured = registration returns 503 and every verify fails, closed.
- **Budget:** the console spend cap on the central key is the hard backstop, but tripping it takes the whole beta down until it resets. This breaker trips first, on trailing-24h `event_costs` > `DAILY_BUDGET_USD`, and recovers on its own. `event_costs` still prices every event at Sonnet's $3/$15 per M tokens (migration 004), so with Sol it overestimates spend (open item). It's cached for 60s, so one aggregate query per minute.
- **Rate limit:** IPv6 is keyed per /64, because privacy extensions mint a fresh address per connection. A malformed IP is used as-is rather than raising.
- **`FREE_LIMIT`** is the default for new users. Raising one local user's count in dev: the `grant-free-messages` skill.
