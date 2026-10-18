import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Self-hosted Postgres (replacing Supabase). Async driver for the app, sync for Alembic.
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

# Cleanup
POST_RETENTION_DAYS = 30

# CORS
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:5175,https://reddit.aishwaryadv.space"
).split(",") if o.strip()]
