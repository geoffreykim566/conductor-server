# evals

Model-in-the-loop evaluation. These hit the real APIs, unlike `tests/`, which are mocked unit tests. Not part of the server image: `evals/` is bind-mounted into the container by `docker-compose.yml`. Output goes to `test_runs/<date>/` (gitignored).

## Files

| Path | What |
|---|---|
| `battery/runner.py` | Runs a scenario set through `respond()` and prints transcripts and verdicts |
| `battery/grader.py` | Turns a trace into an outcome and grades it against the scenario's `expect` block |
| `scenarios/core.json` | **The core battery** (39 scenarios, 48 turns): one or two per distinct behaviour. The regression and quality check |
| `scenarios/extended.json` | Everything else (83). Variations on core behaviours, kept for targeted runs, not run by default |
| `battery/paths.py` | `ungrounded_paths`: menu paths stated with no route or cited source behind them |
| `drive_turn.py` | One turn at a time, with state kept in a file between calls: for reactive multi-turn probing |

## Running the battery

Rebuild first if `app/` or `seed/` changed, or you're grading the old code.

```bash
mkdir -p test_runs/$(date +%F)
docker compose exec -T app python -m evals.battery.runner > test_runs/$(date +%F)/run.log 2>&1   # core (default), ~12 min serial
docker compose exec -T app python -m evals.battery.runner --set extended                         # or: all
docker compose exec -T app python -m evals.battery.runner name1 name2                            # by name, from any set
docker compose exec -T app python -m evals.battery.runner --runs 3 name1                         # flakiness check
```

**Shard it 3-way in parallel** (~5 min for core). Rate limits are not a constraint:

```bash
for i in 0 1 2; do
  NAMES=$(python3 -c "import json;s=json.load(open('evals/scenarios/core.json'));print(' '.join(x['name'] for x in s[$i::3]))")
  docker compose exec -T app python -m evals.battery.runner $NAMES > test_runs/$(date +%F)/run_shard$i.log 2>&1 &
done; wait
grep -c '\[PASS\]' test_runs/$(date +%F)/run_shard*.log; grep -h -B1 '\[FAIL\]' test_runs/$(date +%F)/run_shard*.log
```

Compare against a baseline run of the same scenarios, never against memory. Run core ×2 for a comparison: pass counts move by ±2 between identical runs, so read *which* assertions changed and read the answers themselves.

## Expect keys (`grader.grade`)

| Key | Passes when |
|---|---|
| `walkthrough_destination` | the route(s) on the card include it. `null` = nothing attached; a list = any of them, and `null` in the list means "nothing" is acceptable |
| `walkthrough_destination_absent` | none of these routes are on the card |
| `action_calls` | these action calls happened, in order, as a subsequence. `{"tool", "args": {k: substring}, "ok", "args_absent"}`. `null` = no action calls at all |
| `setting_calls` / `forbidden_setting_calls` | the same for `open_setting` calls (route + dropdown value) |
| `no_action_calls`, `no_refused_actions` | bools |
| `no_completion_claims` | the reply doesn't say a queued action already happened ("is set", "I've loaded"). Substring-brittle |
| `response_contains` / `_any` / `response_not_contains` | case-insensitive substrings of the reply |
| `first_tool` | name, or a list of acceptable names |
| anything else | compared for equality against the outcome: `no_tool_calls`, `web_research_called`, `plugin_read_called`, `confidence_tier`, `sources_present`, `auto_run` |

The runner drives turns like the client: the tool is offered, and a turn parked at `read_plugin_values` is resumed with the turn's `plugin_reads` (`{plugin: {control: value}}`), through the real park/resume path.

A top-level `expect` grades the final turn. A per-turn `expect` grades that turn's own trace.

## Quirks & why

- **`expect` is written before running, never fitted to what happened.** A note that describes behaviour without asserting it is untested; add the assert.
- **The grader keeps its own `ACTION_TOOLS`** rather than importing `app.tools`, so it can grade any build.
- **`battery/paths.py` (`ungrounded_paths`)** reports menu paths an answer states that are in neither its cited text nor a route. It's not asserted.
- **The KB-era keys are gone** (`match`, `resolved_problem`, `walkthrough_solution`, `lookup_count`, 10-17). Five scenarios graded only those and now run ungraded: `multiturn_topic_pivot` (core) and four in extended. Give them real asserts before relying on them. Runs before 10-17 aren't comparable pass-count for pass-count.
- **Known grader issue:** `no_completion_claims` flags descriptive "is set". Read the FAIL before believing it.
- **Code-guaranteed scenarios** (e.g. the toggle gate refusing an attach) pass whatever the model does. They're regression tests for that code path, not model judgment.
- **A/Bs record full answers on identical input.** The KB-era `latency_variants.py` harness was removed with the KB; one-off A/Bs (e.g. the writer A/B, `test_runs/2026-10-17/writer_ab.py`) run the decider once and compare the arms on its output. n=2 per cell can't judge quality; read the answers.

## Adding a scenario

**Don't grow the core battery by default.** The battery used to gain cases with every new feature until it was 118 scenarios, mostly variations on the same few code paths. That made every run slow and expensive without catching more.

- **When you build something new, test it directly:** unit tests in `tests/`, plus a few targeted scenarios you run by name while developing. Put those in `extended.json`.
- **Add to `core.json` only when the scenario exercises behaviour no core scenario covers:** a new code path, a new tool, a new failure class. Not a new phrasing of a covered one. If it replaces a weaker core scenario, swap it rather than add it.
- **Day to day, the core battery is the regression and quality check.** Run it after any pipeline, prompt or route change, and before a merge.
- **Format:** each scenario has a `note` (what it tests and why) and an `expect` written from the desired behaviour. Run a new one alone 3× (`--runs 3`) to check it's stable before relying on it.
