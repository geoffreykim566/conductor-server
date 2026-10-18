"""Pipeline tunables. Always read them as `settings.X` at call time, never
`from ...settings import X`: tests and evals/latency_variants.py patch them on this
module. Why each value is what it is: README.md (Tunables)."""

MAX_ITERATIONS = 6

# Sol's reasoning effort (None sends the model default). Medium: same graded quality
# as high, ~1 s faster median, ~7% cheaper; low was no faster and worse.
DECIDER_EFFORT: str | None = "medium"

# tool_choice for a go-ahead's first call, which must call a tool. None (auto): a first
# call that makes no tool call is re-asked once with TOOL_NUDGE instead. Kept from the
# Sonnet era, which rejected a forced choice; unmeasured forced with Sol.
FORCED_TOOL_CHOICE: dict | None = None
RETRY_NO_TOOL_FIRST_CALL = True

# End the turn after an iteration whose calls were all accepted actions, skipping the
# prose-only follow-up call.
EARLY_EXIT_ON_ACTION = True

# Steps one card may hold.
MAX_ATTACHES_PER_TURN = 6
