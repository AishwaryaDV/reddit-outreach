import logging
from datetime import datetime, timezone

import praw

from app.config import (
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USERNAME, REDDIT_PASSWORD,
    DAILY_DM_CAP, DRY_RUN,
)
from app.database import get_client

logger = logging.getLogger(__name__)

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
    return all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD])


def _sent_today_count() -> int:
    today = datetime.now(tz=timezone.utc).date().isoformat()
    result = (
        get_client()
        .table("messages")
        .select("id", count="exact")
        .eq("status", "sent")
        .gte("updated_at", today)
        .execute()
    )
    return result.count or 0


def _mark_sent(message_id: str, post_id: str):
    get_client().table("messages").update({"status": "sent"}).eq("id", message_id).execute()
    get_client().table("posts").update({"status": "sent"}).eq("id", post_id).execute()


def send_dm(message_id: str, post_id: str, recipient: str, body: str) -> dict:
    """
    Sends a Reddit DM. Returns {"sent": bool, "dry_run": bool, "reason": str}.
    Always dry-runs if credentials are missing or DRY_RUN=true in env.
    """
    effective_dry_run = DRY_RUN or not _credentials_present()

    if effective_dry_run:
        reason = "DRY_RUN=true" if DRY_RUN else "Reddit credentials not configured"
        logger.info(
            "DRY RUN — would send DM to u/%s (message %s): %s",
            recipient, message_id, body[:80],
        )
        _mark_sent(message_id, post_id)
        return {"sent": True, "dry_run": True, "reason": reason}

    sent_today = _sent_today_count()
    if sent_today >= DAILY_DM_CAP:
        logger.warning("Daily DM cap (%d) reached — skipping u/%s", DAILY_DM_CAP, recipient)
        return {"sent": False, "dry_run": False, "reason": f"Daily cap of {DAILY_DM_CAP} reached"}

    try:
        _get_reddit().redditor(recipient).message(
            subject="Quick question about your post",
            message=body,
        )
        _mark_sent(message_id, post_id)
        logger.info("DM sent to u/%s (message %s)", recipient, message_id)
        return {"sent": True, "dry_run": False, "reason": "ok"}
    except Exception as e:
        logger.error("Failed to send DM to u/%s: %s", recipient, e)
        return {"sent": False, "dry_run": False, "reason": str(e)}


def process_auto_sends():
    """Called by scheduler — sends all approved messages past their send_after time."""
    now = datetime.now(tz=timezone.utc).isoformat()
    result = (
        get_client()
        .table("messages")
        .select("id, post_id, final_message, draft, posts(author)")
        .eq("status", "approved")
        .lte("send_after", now)
        .execute()
    )

    rows = result.data or []
    if not rows:
        return

    logger.info("Auto-send: %d message(s) ready", len(rows))
    for row in rows:
        author = (row.get("posts") or {}).get("author", "")
        body = row.get("final_message") or row.get("draft") or ""
        if not author or not body:
            logger.warning("Auto-send skipped message %s — missing author or body", row["id"])
            continue
        send_dm(row["id"], row["post_id"], author, body)
