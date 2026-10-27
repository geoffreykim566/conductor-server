-- Migration 012: one user per Mac. `device_hash` is the client's SHA-256 of the Mac's hardware
-- UUID, so a reinstall (in-app Uninstall wipes the token) registers back to the same user and
-- free count. Install/uninstall/reinstall counts drive the admin page; `installed` is derived
-- so a reinstall keeps the last uninstall date.
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/012_device_identity.sql

alter table users add column if not exists device_hash    text unique;
alter table users add column if not exists uninstalls     int not null default 0;
alter table users add column if not exists reinstalls     int not null default 0;
alter table users add column if not exists reinstalled_at timestamptz;
alter table users add column if not exists installed      boolean
    generated always as (uninstalled_at is null or coalesce(reinstalled_at > uninstalled_at, false)) stored;

-- Rows marked uninstalled before this migration count as one uninstall.
update users set uninstalls = 1 where uninstalled_at is not null and uninstalls = 0;
