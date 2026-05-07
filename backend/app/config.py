import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

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

WATCHER_INTERVAL_MINUTES = 2
APPROVAL_WINDOW_MIN = 10
APPROVAL_WINDOW_MAX = 10
DAILY_DM_CAP = 20
PORTFOLIO_URL = "https://aishwaryadv.space"

# Notifications
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAILS = [e.strip() for e in os.getenv("NOTIFY_EMAILS", "").split(",") if e.strip()]

# Cleanup
POST_RETENTION_DAYS = 5
