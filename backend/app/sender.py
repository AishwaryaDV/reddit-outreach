import asyncio
import logging
import uuid
from datetime import datetime, timezone

import praw
from sqlalchemy import func, select, update

from app.config import (
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USERNAME, REDDIT_PASSWORD,
    DAILY_DM_CAP, DRY_RUN, reddit_configured,
)
from app.database import get_setting
from app.db import get_session_factory
from app.models import Message, Post

logger = logging.getLogger(__name__)

# Max messages sent per 1-minute tick — spreads a backlog over several runs
# instead of firing everything at once (anti-spam).
AUTO_SEND_BATCH = 4

_reddit: praw.Reddit | None = None


def _get_reddit() -> praw.Reddit:
    global _reddit
    if _reddit is None:
        _reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            user_agent="reddit-outreach-personal-tool/1.0",
        )
    return _reddit


def _credentials_present() -> bool:
    return reddit_configured()


async def _sent_today_count() -> int:
    today_start = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    async with get_session_factory()() as session:
        result = await session.execute(
            select(func.count(Message.id)).where(
                Message.status.in_(["sent", "dry_sent"]),
                Message.sent_at >= today_start,
            )
        )
        return result.scalar() or 0


async def _already_messaged(author: str, exclude_post_id: str) -> bool:
    """True if we've already DMed this Reddit user for a different post.

    _mark_sent stamps the post row with sent/dry_sent too, so the posts table
    is the record of who we've contacted. Case-insensitive (Reddit usernames
    are not case-sensitive); dry_sent counts so the guard is testable under DRY_RUN.
    """
    if not author:
        return False
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Post.id)
            .where(
                Post.status.in_(["sent", "dry_sent"]),
                func.lower(Post.author) == author.lower(),
                Post.id != uuid.UUID(str(exclude_post_id)),
            )
            .limit(1)
        )
        return result.first() is not None


async def _mark_cancelled(message_id: str) -> None:
    async with get_session_factory()() as session:
        await session.execute(
            update(Message).where(Message.id == uuid.UUID(str(message_id))).values(status="cancelled")
        )
        await session.commit()


async def _mark_sent(message_id: str, post_id: str, dry_run: bool = False) -> None:
    # dry_sent keeps test sends distinguishable from real CRM history
    status = "dry_sent" if dry_run else "sent"
    sent_at = datetime.now(tz=timezone.utc)
    async with get_session_factory()() as session:
        await session.execute(
            update(Message)
            .where(Message.id == uuid.UUID(str(message_id)))
            .values(status=status, sent_at=sent_at)
        )
        await session.execute(
            update(Post).where(Post.id == uuid.UUID(str(post_id))).values(status=status)
        )
        await session.commit()


async def send_dm(message_id: str, post_id: str, recipient: str, body: str) -> dict:
    """
    Sends a Reddit DM. Returns {"sent": bool, "dry_run": bool, "reason": str}.
    Always dry-runs if credentials are missing or DRY_RUN=true in env.
    """
    effective_dry_run = DRY_RUN or not _credentials_present()

    # Never DM the same Reddit user twice — the top account-ban risk. Same
    # person posting across subreddits would otherwise get one DM per post.
    if await _already_messaged(recipient, post_id):
        logger.info("Skipping u/%s (message %s) — already messaged", recipient, message_id)
        await _mark_cancelled(message_id)
        return {"sent": False, "dry_run": effective_dry_run, "reason": f"Already messaged u/{recipient}"}

    cap = int(await get_setting("daily_dm_cap", str(DAILY_DM_CAP)))
    sent_today = await _sent_today_count()
    if sent_today >= cap:
        logger.warning("Daily DM cap (%d) reached — skipping u/%s", cap, recipient)
        return {"sent": False, "dry_run": effective_dry_run, "reason": f"Daily cap of {cap} reached"}

    if effective_dry_run:
        reason = "DRY_RUN=true" if DRY_RUN else "Reddit credentials not configured"
        logger.info(
            "DRY RUN — would send DM to u/%s (message %s): %s",
            recipient, message_id, body[:80],
        )
        await _mark_sent(message_id, post_id, dry_run=True)
        return {"sent": True, "dry_run": True, "reason": reason}

    try:
        # PRAW is synchronous — keep its network call off the event loop.
        await asyncio.to_thread(
            lambda: _get_reddit().redditor(recipient).message(
                subject="Quick question about your post",
                message=body,
            )
        )
        await _mark_sent(message_id, post_id)
        logger.info("DM sent to u/%s (message %s)", recipient, message_id)
        return {"sent": True, "dry_run": False, "reason": "ok"}
    except Exception as e:
        logger.error("Failed to send DM to u/%s: %s", recipient, e)
        return {"sent": False, "dry_run": False, "reason": str(e)}


async def process_auto_sends() -> None:
    """Called by scheduler — sends messages whose review window has elapsed.

    `pending` = the user never acted within the approval window (implicit
    consent); `approved` = explicitly approved. Disapprove sets `cancelled`,
    excluded here. Capped at AUTO_SEND_BATCH per run.
    """
    now = datetime.now(tz=timezone.utc)
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Message.id, Message.post_id, Message.final_message, Message.draft, Post.author)
            .join(Post, Message.post_id == Post.id)
            .where(
                Message.status.in_(["pending", "approved"]),
                Message.send_after <= now,
            )
            .order_by(Message.send_after)
            .limit(AUTO_SEND_BATCH)
        )
        rows = result.all()

    if not rows:
        return

    logger.info("Auto-send: %d message(s) ready", len(rows))
    for row in rows:
        author = row.author or ""
        body = row.final_message or row.draft or ""
        if not author or not body:
            logger.warning("Auto-send skipped message %s — missing author or body", row.id)
            continue
        await send_dm(str(row.id), str(row.post_id), author, body)
