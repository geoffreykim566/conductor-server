-- Migration 013: free tier goes from 50 to 100 messages (user call 10-30). The limit is copied
-- into each row at register, so existing users are raised too; anyone granted more keeps it.
--
-- Release: after the deploy (the old server registers new users at 50; the new code doesn't need this).
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/013_free_limit_100.sql

alter table users alter column free_limit set default 100;
update users set free_limit = 100 where free_limit < 100;
