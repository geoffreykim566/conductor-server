-- Migration 011: bug reports and feedback sent from the client's "Report Bug" form
-- (POST /v3/feedback). `context` is the client's dump (chat, server transcript, AX state,
-- run log, versions): always on a bug, opt-in on feedback. `read_at` drives the admin
-- tab's unread count.
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/011_feedback.sql

create table if not exists feedback (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references users(id),
    created_at   timestamptz not null default now(),
    kind         text not null check (kind in ('bug', 'feedback')),
    title        text not null,
    message      text,
    app_version  text,
    context      jsonb,
    read_at      timestamptz
);

create index if not exists feedback_created on feedback (created_at desc);
