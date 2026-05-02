import logging
import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.config import WATCHER_INTERVAL_MINUTES
from app.watcher import run_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_watcher, "interval", minutes=WATCHER_INTERVAL_MINUTES, id="watcher")
    scheduler.start()
    logging.info("Watcher scheduler started — running every %d minutes", WATCHER_INTERVAL_MINUTES)
    asyncio.create_task(run_watcher())
    yield
    scheduler.shutdown()
    logging.info("Scheduler stopped")


app = FastAPI(title="Reddit Outreach API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/watcher/run")
async def trigger_watcher():
    asyncio.create_task(run_watcher())
    return {"status": "watcher triggered"}
