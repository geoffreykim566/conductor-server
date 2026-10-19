-- Base schema. Held the KB tables (solutions, problems, problem_solutions) and the
-- vector extension until v042 removed the KB; 010 drops them from existing DBs.

create extension if not exists pgcrypto;
