import logging
import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    WATCHER_INTERVAL_MINUTES, GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAILS,
    APPROVAL_WINDOW_MIN, DAILY_DM_CAP, PORTFOLIO_URL, POST_RETENTION_DAYS, DRY_RUN,
)
from app.watcher import run_watcher, run_cleanup, get_last_run_at, search_term
from app.sender import process_auto_sends, send_dm
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
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "https://reddit.aishwaryadv.space"],
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


@app.get("/config")
def get_config():
    return {
        "watcher_interval_minutes": WATCHER_INTERVAL_MINUTES,
        "approval_window_minutes": APPROVAL_WINDOW_MIN,
        "daily_dm_cap": DAILY_DM_CAP,
        "portfolio_url": PORTFOLIO_URL,
        "post_retention_days": POST_RETENTION_DAYS,
        "gmail_configured": bool(GMAIL_USER and GMAIL_APP_PASSWORD and NOTIFY_EMAILS),
    }


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
