-- Migration 016: voice input. One row per user per local day: seconds claimed against the daily
-- limit (counted from each clip's WAV header before the call) and the seconds OpenAI billed.
-- users.timezone is the IANA name the client sent first; "today" is computed in it, and it's
-- kept so changing the Mac's timezone can't buy extra minutes. Deleted with the user.
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/016_voice_usage.sql

create table if not exists voice_usage (
    user_id         uuid not null references users(id) on delete cascade,
    day             date not null,                      -- the user's local date
    seconds         numeric(8, 2) not null default 0,   -- claimed against the limit
    billed_seconds  numeric(8, 2) not null default 0,   -- from OpenAI's usage, for cost
    clips           int not null default 0,
    updated_at      timestamptz not null default now(),
    primary key (user_id, day)
);

create index if not exists voice_usage_updated on voice_usage (updated_at);

alter table users add column if not exists timezone text;
