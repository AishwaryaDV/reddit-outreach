import os
from dotenv import load_dotenv

load_dotenv()

# Self-hosted Postgres. Async driver for the app, sync for Alembic.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://reddit:reddit@localhost:5432/reddit_outreach"
)
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC", "postgresql+psycopg2://reddit:reddit@localhost:5432/reddit_outreach"
)

SEARCH_TERMS = [
    "hiring developer",
    "hiring engineer",
    "hiring full stack engineer",
    "hiring react developer",
    "hiring web developer",
    "hiring web app developer",
    "hiring remote developer",
    "hiring freelance developer",
    "looking for a website developer",
    "looking for a web app developer",
    "looking for a developer",
    "need a developer",
    "need a web developer",
    "need a fullstack developer",
]

WATCHER_INTERVAL_MINUTES = 10
APPROVAL_WINDOW_MIN = 2
APPROVAL_WINDOW_MAX = 5
DAILY_DM_CAP = 20
PORTFOLIO_URL = "https://aishwaryadv.space"

# Notifications
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAILS = [e.strip() for e in os.getenv("NOTIFY_EMAILS", "").split(",") if e.strip()]

# Reddit DM sender
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"


def reddit_configured() -> bool:
    """True when all four Reddit API credentials are present. Until then the
    watcher makes no requests to Reddit — avoids pointless 403s that can get the
    IP flagged by Reddit's network security."""
    return all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD])

# --- LLM (scorer / judge) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODE = os.getenv("LLM_MODE", "live")  # live | replay (replay serves cached responses, no model calls, no cost)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_FALLBACK_MODELS = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite,gemini-flash-lite-latest")
# Protect the Claude Pro subscription: cap how fast the scorer may hit Claude.
# When the budget for the current minute/hour is used, scoring overflows to
# Gemini immediately — no waiting, no backlog, so a post is never missed.
# Counted from the llm_calls table.
CLAUDE_MAX_PER_MIN = int(os.getenv("CLAUDE_MAX_PER_MIN", "5"))
CLAUDE_MAX_PER_HOUR = int(os.getenv("CLAUDE_MAX_PER_HOUR", "30"))
CLAUDE_MAX_BUDGET_USD = float(os.getenv("CLAUDE_MAX_BUDGET_USD", "0.05"))  # native per-call cap

# Anonymous search.rss pacing — Reddit throttles anonymous search hard, so we query
# one phrase at a time with a gap between, and back off on 429. No login/API needed.
SEARCH_TERM_DELAY_SECONDS = int(os.getenv("SEARCH_TERM_DELAY_SECONDS", "90"))
SEARCH_BACKOFF_SECONDS = int(os.getenv("SEARCH_BACKOFF_SECONDS", "120"))

# Cleanup
POST_RETENTION_DAYS = 30

# CORS
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:5175,https://reddit.aishwaryadv.space"
).split(",") if o.strip()]
