-- Migration 015: the visits → installs funnel. `visits` holds one row per counted page view from
-- the site's beacon (bots dropped before insert, no IP stored). `channel` is the normalised
-- source (app/core/channel.py); `country` comes from the IP at signup/register, which is dropped.
-- users.channel is copied from the Mac's waitlist row at register: a label, never the email.
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/015_funnel.sql

create table if not exists visits (
    id            bigserial primary key,
    created_at    timestamptz not null default now(),
    visitor_id    uuid not null,     -- random, kept in the browser's local storage: one per browser
    session_id    uuid not null,     -- random, per tab (session storage): one visit
    path          text not null,     -- '/', '/download', '/privacy' or 'other'
    channel       text not null,
    utm_source    text,
    utm_medium    text,
    utm_campaign  text,
    referrer_host text,
    country       text,
    device        text               -- desktop | mobile | tablet
);

create index if not exists visits_created on visits (created_at);
create index if not exists visits_visitor on visits (visitor_id, created_at);

alter table waitlist add column if not exists channel text;
alter table waitlist add column if not exists country text;
alter table users    add column if not exists channel text;
alter table users    add column if not exists country text;
