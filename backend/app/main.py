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
from app.scorer import SCORER_MODE
from app.sender import process_auto_sends, send_dm
from pydantic import BaseModel
import uuid

from sqlalchemy import select

from app.database import get_setting, set_setting
from app.db import get_session_factory
from app.models import Message, Post

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
        "scorer": SCORER_MODE,
        "gmail_configured": bool(GMAIL_USER and GMAIL_APP_PASSWORD and NOTIFY_EMAILS),
        "watcher_interval_minutes": WATCHER_INTERVAL_MINUTES,
        "last_run_at": get_last_run_at(),
    }


async def _get_live_config():
    return {
        "portfolio_url": await get_setting("portfolio_url", PORTFOLIO_URL),
        "daily_dm_cap": int(await get_setting("daily_dm_cap", str(DAILY_DM_CAP))),
        "approval_window_min": int(await get_setting("approval_window_min", str(APPROVAL_WINDOW_MIN))),
        "approval_window_max": int(await get_setting("approval_window_max", str(APPROVAL_WINDOW_MAX))),
        "watcher_interval_minutes": WATCHER_INTERVAL_MINUTES,
        "post_retention_days": POST_RETENTION_DAYS,
        "gmail_configured": bool(GMAIL_USER and GMAIL_APP_PASSWORD and NOTIFY_EMAILS),
    }


@app.get("/config")
async def get_config():
    return await _get_live_config()


class ConfigUpdate(BaseModel):
    key: str
    value: str


@app.post("/config")
async def update_config(body: ConfigUpdate):
    allowed = {"portfolio_url", "daily_dm_cap", "approval_window_min", "approval_window_max"}
    if body.key not in allowed:
        raise HTTPException(status_code=400, detail=f"Key '{body.key}' is not editable")
    await set_setting(body.key, body.value)
    return await _get_live_config()


@app.get("/notifications/status")
async def notifications_status():
    enabled = await get_setting("notifications_enabled", "true") == "true"
    return {"enabled": enabled}


@app.post("/notifications/toggle")
async def notifications_toggle():
    current = await get_setting("notifications_enabled", "true")
    new_value = "false" if current == "true" else "true"
    await set_setting("notifications_enabled", new_value)
    return {"enabled": new_value == "true"}


@app.post("/messages/{message_id}/send")
async def manual_send(message_id: str):
    try:
        mid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found or not in sendable state")

    async with get_session_factory()() as session:
        result = await session.execute(
            select(Message.id, Message.post_id, Message.final_message, Message.draft, Post.author)
            .join(Post, Message.post_id == Post.id)
            .where(Message.id == mid, Message.status.in_(["approved", "pending"]))
        )
        row = result.first()

    if row is None:
        raise HTTPException(status_code=404, detail="Message not found or not in sendable state")

    author = row.author or ""
    body = row.final_message or row.draft or ""
    if not author or not body:
        raise HTTPException(status_code=422, detail="Missing author or message body")

    return await send_dm(str(row.id), str(row.post_id), author, body)


@app.get("/search/reddit")
async def search_reddit(q: str):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    count = await search_term(q.strip())
    return {"status": "done", "term": q.strip(), "new_posts": count}


@app.post("/watcher/run")
async def trigger_watcher():
    _spawn(run_watcher())
    return {"status": "watcher triggered"}


@app.post("/watcher/backfill")
async def trigger_backfill():
    _spawn(run_watcher(time_filter="day"))
    return {"status": "backfill triggered — searching all terms for past 24h"}
