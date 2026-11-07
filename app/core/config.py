"""Server configuration. Secrets come from the environment (.env.local locally), never the repo.
Why each value is what it is: app/core/README.md."""
import os

CONDUCTOR_ID_SECRET = os.environ.get("CONDUCTOR_ID_SECRET", "")
RATE_LIMIT = os.environ.get("RATE_LIMIT", "10/minute")
# 20, not 5: a mistyped email on the setup screen is retried through register.
REGISTER_RATE_LIMIT = os.environ.get("REGISTER_RATE_LIMIT", "20/day")
FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT", "10/hour")
WAITLIST_RATE_LIMIT = os.environ.get("WAITLIST_RATE_LIMIT", "10/hour")
# A page load sends one beacon; this caps a script replaying it from one address.
VISIT_RATE_LIMIT = os.environ.get("VISIT_RATE_LIMIT", "120/hour")

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

# Waitlist gate: a new Mac registers only with an approved email, at most this many Macs each.
WAITLIST_REQUIRED = os.environ.get("WAITLIST_REQUIRED", "1") == "1"
WAITLIST_INSTALL_CAP = int(os.environ.get("WAITLIST_INSTALL_CAP", "2"))
# The landing page posts the signup form cross-origin; local previews serve on :8765.
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "https://askconductor.ai,https://www.askconductor.ai,http://127.0.0.1:8765,http://localhost:8765",
).split(",")

# Invite emails (Resend). Unset key: approving works, emailing is refused.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
INVITE_FROM = os.environ.get("INVITE_FROM", "Conductor <hello@askconductor.ai>")
INVITE_REPLY_TO = os.environ.get("INVITE_REPLY_TO", "hello@askconductor.ai")
DOWNLOAD_URL = os.environ.get("DOWNLOAD_URL", "https://askconductor.ai/download")

# DB-IP Lite country database, downloaded at image build (Dockerfile). Outside /srv so the
# standalone stack's bind mount doesn't hide it.
GEO_DB_PATH = os.environ.get("GEO_DB_PATH", "/opt/geo/dbip-country-lite.mmdb")
