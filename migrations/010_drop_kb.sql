-- Migration 010: drop the KB tables and the vector extension. v042 removed the KB and its
-- vector lookup (Sol answers from its own knowledge), so nothing reads them. The KB content
-- is kept in ~/Desktop/OLD Conductor/kb-2026-10-17/.
-- Release: after the deploy. Servers before v042 register the vector type on every connection.
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/010_drop_kb.sql

drop table if exists problem_solutions;
drop table if exists problems;
drop table if exists solutions;
drop table if exists query_log;
drop extension if exists vector;
