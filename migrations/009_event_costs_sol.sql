-- Migration 009: price events at the model that served them (Sol since v042), counting cached input.
--
-- 004 priced every event at Sonnet's $3/$15 per M and never saw cached input (only uncached
-- tokens were stored), so the budget breaker overestimated Sol's spend. Rates are OpenAI's
-- standard tier for gpt-6.1-sol (<=272K-token input; our calls are ~10K): $2 in, $0.10 cached,
-- $10 out. Older claude-* rows keep 004's rates so the admin history doesn't shift.
-- Web-search fees ($10 / 1k calls) aren't counted (research is rare; a few % of spend).
--
-- Existing DB: docker compose exec -T db psql -U conductor -d conductor -1 < migrations/009_event_costs_sol.sql

alter table events add column if not exists tokens_cached integer not null default 0;

-- Dropped, not replaced: the new column lands where usd_cost was, which create or replace refuses.
drop view if exists event_costs;
create view event_costs as
select e.*,
    case when e.model like 'claude%' then
        round(e.tokens_in / 1e6 * 3.00, 6) + round(e.tokens_out / 1e6 * 15.00, 6)
    else
        round(e.tokens_in / 1e6 * 2.00, 6) + round(e.tokens_cached / 1e6 * 0.10, 6)
        + round(e.tokens_out / 1e6 * 10.00, 6)
    end as usd_cost
from events e;
