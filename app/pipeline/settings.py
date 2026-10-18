"""Pipeline tunables. Always read them as `settings.X` at call time, never
`from ...settings import X`: tests and evals/latency_variants.py patch them on this
module. Why each value is what it is: README.md (Tunables)."""
import os

MAX_ITERATIONS = 6

# Decider-only request knobs (None omits the param). Effort medium: same graded
# quality as high, ~1 s faster median, ~7% cheaper; low was no faster and worse.
DECIDER_EFFORT: str | None = "medium"
DECIDER_THINKING: dict | None = None

# tool_choice for the calls that must call a tool (a go-ahead's first call, the
# pick re-ask). Sonnet 5.5 rejects forced tool_choice with a 400, so it's None
# (auto) and a first call that makes no tool call is re-asked once instead.
FORCED_TOOL_CHOICE: dict | None = None
RETRY_NO_TOOL_FIRST_CALL = True

# End the turn after an iteration whose calls were all accepted actions and/or
# citations (with text written), skipping the prose-only follow-up call.
EARLY_EXIT_ON_ACTION = True

# Steps one card may hold.
MAX_ATTACHES_PER_TURN = 6

# Tell the writer to hedge on "moderate" turns. Off: the tier over-fires on observations.
HEDGE_MODERATE_TURNS = False

# Writer A/B for the Sol decider (sol-log.md, 10-17); env so battery processes can differ.
# SOL_WRITER "none": Sol's text goes out as written. WRITER_MODEL overrides config.WRITER_MODEL.
# WRITER_CARD_V2: the card block keeps the text's manual steps and questions, and carries no option note.
SOL_WRITER: str = os.environ.get("SOL_WRITER", "haiku")
WRITER_MODEL: str | None = os.environ.get("WRITER_MODEL") or None
WRITER_CARD_V2: bool = os.environ.get("WRITER_CARD_V2") == "1"
