-- Migration 014: the waitlist. The landing page adds an email (POST /v3/waitlist); the admin
-- approves it and emails the download link; a new Mac registers only with an approved email
-- under the install cap. Deliberately not linked to `users`: usage data stays pseudonymous.
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/014_waitlist.sql

create table if not exists waitlist (
    id           uuid primary key default gen_random_uuid(),
    email        text not null unique,          -- trimmed and lowercased
    created_at   timestamptz not null default now(),
    source       text,                          -- utm_source or referrer host, if the page had one
    approved_at  timestamptz,                   -- null = still on the waitlist
    emailed_at   timestamptz,                   -- when the invite email was last sent
    installs     int not null default 0         -- new Macs registered with this email
);

create index if not exists waitlist_created on waitlist (created_at desc);
