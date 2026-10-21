import logging
import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    WATCHER_INTERVAL_MINUTES, GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAILS,
    APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX, DAILY_DM_CAP, DAILY_LLM_CAP,
    PORTFOLIO_URL, POST_RETENTION_DAYS, DRY_RUN, CORS_ORIGINS,
)
from app.watcher import run_watcher, run_cleanup, get_last_run_at, search_term
from app.scorer import SCORER_MODE
from app.sender import process_auto_sends, send_dm
from pydantic import BaseModel
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, func, nulls_last, or_, select, update
from sqlalchemy.orm import selectinload

from app.database import get_setting, set_setting
from app.db import get_session_factory
from app.models import LLMCall, Message, Post, SearchTerm
from app.schemas import (
    ApproveIn, MessageOut, MessageWithPost, OutcomeIn,
    PostOut, PostsPage, SearchTermIn, SearchTermOut, SearchTermPatch,
)

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
    # Backfill the last 24h on boot so downtime doesn't lose posts (the 10-min
    # scheduled runs use the tighter 'hour' window for freshness).
    _spawn(run_watcher(time_filter="day"))
    yield
    scheduler.shutdown()
    logging.info("Scheduler stopped")


app = FastAPI(title="Reddit Outreach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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
        "auto_send_enabled": (await get_setting("auto_send_enabled", "false")) == "true",
        "scoring_enabled": (await get_setting("scoring_enabled", "true")) == "true",
        "watcher_interval_minutes": WATCHER_INTERVAL_MINUTES,
        "post_retention_days": POST_RETENTION_DAYS,
        "daily_llm_cap": DAILY_LLM_CAP,
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
    allowed = {
        "portfolio_url", "daily_dm_cap", "approval_window_min", "approval_window_max",
        "auto_send_enabled", "scoring_enabled",
    }
    if body.key not in allowed:
        raise HTTPException(status_code=400, detail=f"Key '{body.key}' is not editable")
    await set_setting(body.key, body.value)
    return await _get_live_config()


@app.get("/notifications/status")
async def notifications_status():
    enabled = await get_setting("notifications_enabled", "false") == "true"
    return {"enabled": enabled}


@app.post("/notifications/toggle")
async def notifications_toggle():
    current = await get_setting("notifications_enabled", "false")
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
async def trigger_watcher(time: str = "hour"):
    # Manual Reddit fetch over a chosen window (maps to Reddit's search time
    # filter). Defaults to 'hour' to match the auto-sweep.
    tf = time if time in ("hour", "day", "week", "month", "all") else "hour"
    _spawn(run_watcher(time_filter=tf))
    return {"status": f"watcher triggered ({tf})"}


@app.post("/watcher/backfill")
async def trigger_backfill():
    _spawn(run_watcher(time_filter="day"))
    return {"status": "backfill triggered — searching all terms for past 24h"}


# --- Data API (replaces the frontend's former direct Supabase access) ---

PAGE_SIZE = 50


def _uuid_or_404(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")


def _message_with_post(m: Message) -> MessageWithPost:
    return MessageWithPost(
        **MessageOut.model_validate(m).model_dump(),
        posts=PostOut.model_validate(m.post) if m.post else None,
    )


@app.get("/posts", response_model=PostsPage)
async def list_posts(
    tab: str = "all",
    time: str = "today",
    q: str = "",
    sort: str = "newest",
    offset: int = 0,
    limit: int = PAGE_SIZE,
):
    now = datetime.now(tz=timezone.utc)
    conditions = []
    if tab == "drafts":
        conditions.append(Post.status == "drafted")
        conditions.append(Post.detected_at < now - timedelta(days=1))
    else:
        if time == "hour":
            conditions.append(Post.detected_at >= now - timedelta(hours=1))
        elif time == "today":
            conditions.append(Post.detected_at >= now - timedelta(days=1))
        if tab == "approved":
            conditions.append(Post.status.in_(["approved", "sent", "dry_sent"]))
        elif tab == "disapproved":
            conditions.append(Post.status == "cancelled")
        elif tab == "rejected":
            conditions.append(Post.status == "rejected")
        else:  # "all" — opportunities only; keep the reject noise out of the feed
            conditions.append(Post.status != "rejected")

    term = q.strip()
    if term:
        # Escape LIKE wildcards so punctuation (., +, (), etc.) is searched literally
        # instead of being stripped, while % and _ can't act as wildcards.
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                Post.title.ilike(pattern, escape="\\"),
                Post.subreddit.ilike(pattern, escape="\\"),
                Post.author.ilike(pattern, escape="\\"),
            )
        )

    order = Post.posted_at.asc() if sort == "oldest" else Post.posted_at.desc()
    async with get_session_factory()() as session:
        total = await session.scalar(select(func.count(Post.id)).where(*conditions))
        result = await session.execute(
            select(Post).where(*conditions).order_by(order).offset(offset).limit(limit)
        )
        posts = result.scalars().all()
    return PostsPage(posts=[PostOut.model_validate(p) for p in posts], total=total or 0)


@app.get("/posts/{post_id}", response_model=PostOut)
async def get_post(post_id: str):
    pid = _uuid_or_404(post_id)
    async with get_session_factory()() as session:
        post = await session.get(Post, pid)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.get("/posts/{post_id}/message", response_model=MessageOut | None)
async def get_post_message(post_id: str):
    pid = _uuid_or_404(post_id)
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Message)
            .where(Message.post_id == pid)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


@app.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    pid = _uuid_or_404(post_id)
    async with get_session_factory()() as session:
        await session.execute(delete(Post).where(Post.id == pid))  # messages cascade via FK
        await session.commit()
    return {"deleted": True}


@app.post("/messages/{message_id}/approve")
async def approve_message(message_id: str, body: ApproveIn):
    mid = _uuid_or_404(message_id)
    async with get_session_factory()() as session:
        msg = await session.get(Message, mid)
        if msg is None:
            raise HTTPException(status_code=404, detail="Message not found")
        msg.status = "approved"
        if body.final_message is not None:
            msg.final_message = body.final_message
        await session.execute(update(Post).where(Post.id == msg.post_id).values(status="approved"))
        await session.commit()
    return {"status": "approved"}


@app.post("/posts/{post_id}/cancel")
async def cancel_post(post_id: str):
    # Disapprove is a post-level action: cancel the post and any messages it has,
    # so it works even for a post with no draft/message.
    pid = _uuid_or_404(post_id)
    async with get_session_factory()() as session:
        post = await session.get(Post, pid)
        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")
        post.status = "cancelled"
        await session.execute(update(Message).where(Message.post_id == pid).values(status="cancelled"))
        await session.commit()
    return {"status": "cancelled"}


@app.post("/messages/{message_id}/outcome")
async def set_message_outcome(message_id: str, body: OutcomeIn):
    mid = _uuid_or_404(message_id)
    async with get_session_factory()() as session:
        result = await session.execute(
            update(Message).where(Message.id == mid).values(outcome=body.outcome or None)
        )
        await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"outcome": body.outcome or None}


@app.get("/queue", response_model=list[MessageWithPost])
async def get_queue():
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Message)
            .where(Message.status == "approved")
            .order_by(Message.send_after.asc())
            .options(selectinload(Message.post))
        )
        return [_message_with_post(m) for m in result.scalars().all()]


@app.get("/tracker", response_model=list[MessageWithPost])
async def get_tracker():
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Message)
            .where(Message.status.in_(["sent", "dry_sent"]))
            .order_by(nulls_last(Message.sent_at.desc()))
            .options(selectinload(Message.post))
        )
        return [_message_with_post(m) for m in result.scalars().all()]


@app.get("/search-terms", response_model=list[SearchTermOut])
async def list_search_terms():
    async with get_session_factory()() as session:
        result = await session.execute(select(SearchTerm).order_by(SearchTerm.created_at.asc()))
        return result.scalars().all()


@app.post("/search-terms", response_model=SearchTermOut, status_code=201)
async def add_search_term(body: SearchTermIn):
    term = body.term.strip().lower()
    if not term:
        raise HTTPException(status_code=400, detail="Term cannot be empty")
    async with get_session_factory()() as session:
        exists = await session.scalar(select(SearchTerm.id).where(SearchTerm.term == term))
        if exists:
            raise HTTPException(status_code=409, detail="Term already exists")
        st = SearchTerm(term=term, active=True)
        session.add(st)
        await session.flush()
        await session.refresh(st)
        out = SearchTermOut.model_validate(st)
        await session.commit()
    return out


@app.patch("/search-terms/{term_id}", response_model=SearchTermOut)
async def update_search_term(term_id: str, body: SearchTermPatch):
    tid = _uuid_or_404(term_id)
    async with get_session_factory()() as session:
        st = await session.get(SearchTerm, tid)
        if st is None:
            raise HTTPException(status_code=404, detail="Search term not found")
        st.active = body.active
        await session.commit()
        await session.refresh(st)
        return SearchTermOut.model_validate(st)


@app.delete("/search-terms/{term_id}")
async def delete_search_term(term_id: str):
    tid = _uuid_or_404(term_id)
    async with get_session_factory()() as session:
        await session.execute(delete(SearchTerm).where(SearchTerm.id == tid))
        await session.commit()
    return {"deleted": True}


@app.get("/metrics")
async def metrics():
    now = datetime.now(tz=timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    async with get_session_factory()() as s:
        total_calls = await s.scalar(select(func.count(LLMCall.id))) or 0
        today_calls = await s.scalar(select(func.count(LLMCall.id)).where(LLMCall.created_at >= today)) or 0
        total_cost = float(await s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0))) or 0)
        today_cost = float(await s.scalar(
            select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(LLMCall.created_at >= today)) or 0)
        parse_ok = await s.scalar(select(func.count(LLMCall.id)).where(LLMCall.parse_ok.is_(True))) or 0
        fell_back = await s.scalar(select(func.count(LLMCall.id)).where(LLMCall.fell_back.is_(True))) or 0
        p50 = await s.scalar(select(func.percentile_cont(0.5).within_group(LLMCall.latency_ms.asc()))
                             .where(LLMCall.latency_ms.isnot(None)))
        p95 = await s.scalar(select(func.percentile_cont(0.95).within_group(LLMCall.latency_ms.asc()))
                             .where(LLMCall.latency_ms.isnot(None)))
        by_backend = dict((await s.execute(
            select(LLMCall.backend, func.count(LLMCall.id)).group_by(LLMCall.backend))).all())
        day = func.date_trunc("day", LLMCall.created_at, "UTC")  # bucket by UTC day to match the quota counter
        per_day = (await s.execute(
            select(day.label("d"), func.count(LLMCall.id), func.coalesce(func.sum(LLMCall.cost_usd), 0))
            .where(LLMCall.created_at >= now - timedelta(days=14)).group_by(day).order_by(day))).all()
        posts_by_status = dict((await s.execute(
            select(Post.status, func.count(Post.id)).group_by(Post.status))).all())
        msgs_by_status = dict((await s.execute(
            select(Message.status, func.count(Message.id)).group_by(Message.status))).all())
        bucket = case((Post.score >= 8, "8-10"), (Post.score >= 5, "5-7"),
                      (Post.score >= 3, "3-4"), else_="1-2")
        buckets = (await s.execute(
            select(bucket.label("b"), func.count(Post.id),
                   func.count(Post.id).filter(Post.status.in_(["approved", "sent", "dry_sent"])))
            .where(Post.score.isnot(None)).group_by(bucket))).all()
        rejects_by_score = (await s.execute(
            select(Post.score, func.count(Post.id))
            .where(Post.status == "rejected").group_by(Post.score).order_by(Post.score))).all()
    return {
        "calls": {
            "total": total_calls, "today": today_calls,
            "parse_ok_pct": round(parse_ok / total_calls * 100, 1) if total_calls else None,
            "fell_back": fell_back, "by_backend": by_backend,
        },
        "cost": {"total_usd": round(total_cost, 4), "today_usd": round(today_cost, 4)},
        "latency_ms": {"p50": int(p50) if p50 is not None else None,
                       "p95": int(p95) if p95 is not None else None},
        "per_day": [{"day": d.strftime("%Y-%m-%d"), "calls": c, "cost": round(float(cost), 4)}
                    for d, c, cost in per_day],
        "funnel": {"posts": posts_by_status, "messages": msgs_by_status},
        "approve_rate_by_bucket": [{"bucket": b, "total": t, "approved": a} for b, t, a in buckets],
        "rejects_by_score": {str(sc): c for sc, c in rejects_by_score},
        "quota": {"daily_cap": DAILY_LLM_CAP, "today": today_calls, "paused": today_calls >= DAILY_LLM_CAP},
    }
