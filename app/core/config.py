"""Server configuration. Secrets come from the environment (.env.local locally), never the repo.
Why each value is what it is: app/core/README.md."""
import os

CONDUCTOR_ID_SECRET = os.environ.get("CONDUCTOR_ID_SECRET", "")
RATE_LIMIT = os.environ.get("RATE_LIMIT", "10/minute")
REGISTER_RATE_LIMIT = os.environ.get("REGISTER_RATE_LIMIT", "5/day")
FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT", "10/hour")

# Trailing-24h spend (event_costs) above this makes /v3/chat return 503.
DAILY_BUDGET_USD = float(os.environ.get("DAILY_BUDGET_USD", "10"))
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://conductor:conductor@localhost:5432/conductor"
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# The decider: GPT-6.1 Sol on OpenAI's Responses API, no KB (app/pipeline/README.md).
SOL_MODEL = "gpt-6.1-sol"
# Responses counts reasoning in output tokens; 3072 left too little room.
SOL_MAX_OUTPUT_TOKENS = 8192
# web_research's nested call is Sol with OpenAI's web_search tool; it only extracts
# findings, so low effort (app/research/README.md).
RESEARCH_EFFORT = "low"
# 90s timed out every real research call (Claude era); kept as the ceiling.
RESEARCH_CALL_TIMEOUT_S = float(os.environ.get("RESEARCH_CALL_TIMEOUT_S", "90.0"))

FREE_LIMIT = int(os.environ.get("FREE_LIMIT", "100"))

# /admin basic auth. An unset password locks everyone out.
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Optional ping per bug report / feedback (a Discord or Slack incoming webhook). Unset: no ping.
FEEDBACK_WEBHOOK_URL = os.environ.get("FEEDBACK_WEBHOOK_URL", "")
# Where the ping's admin link points.
ADMIN_BASE_URL = os.environ.get("ADMIN_BASE_URL", "https://api.askconductor.ai")

# Cap on round-tripped history (api/history.py trims to this).
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "60"))
