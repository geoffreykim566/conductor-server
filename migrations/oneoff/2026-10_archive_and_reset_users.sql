-- One-off for the v0.4.3 release (user call 10-26): archive users and events, then start the
-- per-Mac counts from zero. Run once on prod after 011 and 012, before the deploy.
-- Everyone's free messages reset: an old token self-heals into a fresh row (api/deps.py).
-- Re-running fails on the existing archive tables, so it can't wipe twice.
--
-- docker compose exec -T db psql -U conductor -d conductor -1 -v ON_ERROR_STOP=1 < migrations/oneoff/2026-10_archive_and_reset_users.sql

create schema if not exists archive;
create table archive.users_2026_10  as select * from users;
create table archive.events_2026_10 as select * from events;
truncate users cascade;  -- also events and feedback
