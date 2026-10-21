"""Pipeline tunables. Always read them as `settings.X` at call time, never
`from ...settings import X`: tests patch them on this module. Why each value is what it is: README.md (Tunables)."""

MAX_ITERATIONS = 6

# Sol's reasoning effort (None sends the model default). Medium: same graded quality
# as high, ~1 s faster median, ~7% cheaper; low was no faster and worse.
DECIDER_EFFORT: str | None = "medium"

# End the turn after an iteration whose calls were all accepted actions, skipping the
# prose-only follow-up call.
EARLY_EXIT_ON_ACTION = True

# Steps one card may hold.
MAX_ATTACHES_PER_TURN = 6
