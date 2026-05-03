import logging
import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import WATCHER_INTERVAL_MINUTES, GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAILS
from app.watcher import run_watcher, run_cleanup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_watcher, "interval", minutes=WATCHER_INTERVAL_MINUTES, id="watcher")
    scheduler.add_job(run_cleanup, "cron", hour=3, minute=0, id="cleanup")
    scheduler.start()
    logging.info("Watcher scheduler started — running every %d minutes", WATCHER_INTERVAL_MINUTES)
    asyncio.create_task(run_watcher())
    yield
    scheduler.shutdown()
    logging.info("Scheduler stopped")


app = FastAPI(title="Reddit Outreach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "https://reddit.aishwaryadv.space"],
    allow_methods=["GET"],
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
    }


@app.get("/watcher/run")
async def trigger_watcher():
    asyncio.create_task(run_watcher())
    return {"status": "watcher triggered"}
