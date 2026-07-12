import logging
import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    WATCHER_INTERVAL_MINUTES, GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAILS,
    APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX, DAILY_DM_CAP, PORTFOLIO_URL, POST_RETENTION_DAYS, DRY_RUN,
    CORS_ORIGINS,
)
from app.watcher import run_watcher, run_cleanup, get_last_run_at, search_term
from app.sender import process_auto_sends, send_dm
from pydantic import BaseModel
from app.database import get_client, get_setting, set_setting

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

scheduler = AsyncIOScheduler()

# asyncio only holds weak refs to tasks — keep strong refs so background
# runs aren't garbage-collected mid-execution
_background_tasks: set = set()


def _spawn(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_watcher, "interval", minutes=WATCHER_INTERVAL_MINUTES, id="watcher")
    scheduler.add_job(run_cleanup, "cron", hour=3, minute=0, id="cleanup")
    scheduler.add_job(process_auto_sends, "interval", minutes=1, id="auto_send")
    scheduler.start()
    logging.info("Watcher scheduler started — running every %d minutes", WATCHER_INTERVAL_MINUTES)
    _spawn(run_watcher())
    yield
    scheduler.shutdown()
    logging.info("Scheduler stopped")


app = FastAPI(title="Reddit Outreach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    return {
        "scorer": "claude-agent-sdk",
        "gmail_configured": bool(GMAIL_USER and GMAIL_APP_PASSWORD and NOTIFY_EMAILS),
        "watcher_interval_minutes": WATCHER_INTERVAL_MINUTES,
        "last_run_at": get_last_run_at(),
    }


def _get_live_config():
    return {
        "portfolio_url": get_setting("portfolio_url", PORTFOLIO_URL),
        "daily_dm_cap": int(get_setting("daily_dm_cap", str(DAILY_DM_CAP))),
        "approval_window_min": int(get_setting("approval_window_min", str(APPROVAL_WINDOW_MIN))),
        "approval_window_max": int(get_setting("approval_window_max", str(APPROVAL_WINDOW_MAX))),
        "watcher_interval_minutes": WATCHER_INTERVAL_MINUTES,
        "post_retention_days": POST_RETENTION_DAYS,
        "gmail_configured": bool(GMAIL_USER and GMAIL_APP_PASSWORD and NOTIFY_EMAILS),
    }


@app.get("/config")
def get_config():
    return _get_live_config()


class ConfigUpdate(BaseModel):
    key: str
    value: str


@app.post("/config")
def update_config(body: ConfigUpdate):
    allowed = {"portfolio_url", "daily_dm_cap", "approval_window_min", "approval_window_max"}
    if body.key not in allowed:
        raise HTTPException(status_code=400, detail=f"Key '{body.key}' is not editable")
    set_setting(body.key, body.value)
    return _get_live_config()


@app.get("/notifications/status")
def notifications_status():
    enabled = get_setting("notifications_enabled", "true") == "true"
    return {"enabled": enabled}


@app.post("/notifications/toggle")
def notifications_toggle():
    current = get_setting("notifications_enabled", "true")
    new_value = "false" if current == "true" else "true"
    set_setting("notifications_enabled", new_value)
    return {"enabled": new_value == "true"}


@app.post("/messages/{message_id}/send")
async def manual_send(message_id: str):
    # .single() raises on zero rows — use maybe_single so a missing/already-sent
    # message returns a proper 404 instead of a 500
    result = (
        get_client()
        .table("messages")
        .select("id, post_id, final_message, draft, posts(author)")
        .eq("id", message_id)
        .in_("status", ["approved", "pending"])
        .maybe_single()
        .execute()
    )
    row = result.data if result else None
    if not row:
        raise HTTPException(status_code=404, detail="Message not found or not in sendable state")

    author = (row.get("posts") or {}).get("author", "")
    body = row.get("final_message") or row.get("draft") or ""
    if not author or not body:
        raise HTTPException(status_code=422, detail="Missing author or message body")

    outcome = send_dm(row["id"], row["post_id"], author, body)
    return outcome


@app.get("/search/reddit")
async def search_reddit(q: str):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    count = await search_term(q.strip())
    return {"status": "done", "term": q.strip(), "new_posts": count}


@app.get("/watcher/run")
async def trigger_watcher():
    _spawn(run_watcher())
    return {"status": "watcher triggered"}


@app.get("/watcher/backfill")
async def trigger_backfill():
    _spawn(run_watcher(time_filter="day"))
    return {"status": "backfill triggered — searching all terms for past 24h"}
