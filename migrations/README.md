# migrations

Plain SQL files, applied in filename order. There's no migration runner.

- **Local:** mounted as `docker-entrypoint-initdb.d`, so they run **only when the DB volume is first created**. On an existing volume, apply a new file by hand:
  `docker compose exec -T db psql -U conductor -d conductor < migrations/00N_name.sql`
- **Prod (Railway):** apply by hand the same way, against the prod DB, as part of the release. A missing migration fails silently at runtime (every lookup failed once because 008 hadn't been applied).
- **Release order: migrate, then deploy.** New code may query new columns. The exception is a migration that removes something the *old* code still uses: apply it after the deploy. 010 is one: servers before v042 register the vector type on every connection.
- **The prod DB is the Railway service `pgvector`.** The name is from the KB era; the vector extension is gone (010). Don't rename it: `DATABASE_URL` points at its hostname.
- **001/002/005/006/008 are comment-only.** They built the KB tables that 010 drops. They stay as no-ops so the numbering holds, and so a fresh volume doesn't need the vector extension.

## One-off scripts (`oneoff/`)

Data changes that run once on prod at a release, not schema: the release skill applies them after the numbered files, with a backup first and the user's go-ahead (step 5b). They are not idempotent on purpose, and the subfolder keeps them out of `docker-entrypoint-initdb.d` (it only runs top-level files).
- `2026-10_archive_and_reset_users.sql` (v0.4.3, user call 10-26): copies `users` and `events` into schema `archive`, then empties `users`, `events` and `feedback`, so per-Mac counts start clean and everyone's free messages reset.

## Adding one

Name it `00N_what_it_does.sql`, the next number. Make it idempotent where you can (`add column if not exists`), since it may be re-applied by hand. If the old server would break once it runs (it removes something the old code uses), add a header line `-- Release: after the deploy`; the release skill applies those after the new server is live. Apply it to the local DB, then rebuild.
