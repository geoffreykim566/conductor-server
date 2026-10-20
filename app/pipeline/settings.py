"""Pipeline tunables. Always read them as `settings.X` at call time, never
`from ...settings import X`: tests and evals/latency_variants.py patch them on this
module. Why each value is what it is: README.md (Tunables)."""

MAX_ITERATIONS = 6

# Sol's reasoning effort (None sends the model default). Medium: same graded quality
# as high, ~1 s faster median, ~7% cheaper; low was no faster and worse.
DECIDER_EFFORT: str | None = "medium"

# tool_choice for a go-ahead's first call. None (auto). Sonnet rejected a forced choice;
# unmeasured forced with Sol.
FORCED_TOOL_CHOICE: dict | None = None
# Re-ask a go-ahead's no-tool first call with TOOL_NUDGE. Off: with Sol the re-ask replaced
# a real reply (README: Forced first call).
RETRY_NO_TOOL_FIRST_CALL = False

# End the turn after an iteration whose calls were all accepted actions, skipping the
# prose-only follow-up call.
EARLY_EXIT_ON_ACTION = True

# Steps one card may hold.
MAX_ATTACHES_PER_TURN = 6

# Offer read_plugin_values to Sol. Off until the client can run the read (plugin-values-log
# step 3); the battery turns it on.
PLUGIN_READS = False
