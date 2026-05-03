import asyncio
import logging
from datetime import datetime, timezone, timedelta
from random import randint

import httpx

from app.config import SEARCH_TERMS, APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX
from app.database import post_exists, save_post, save_message, get_recent_drafts, purge_old_posts
from app.scorer import score_and_draft
from app.notifications import send_notification

logger = logging.getLogger(__name__)

REDDIT_HEADERS = {"User-Agent": "reddit-outreach-personal-tool/1.0"}
REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"


async def fetch_posts(term: str, time_filter: str = "hour") -> list[dict]:
    params = {"q": term, "sort": "new", "t": time_filter, "limit": 25}
    async with httpx.AsyncClient(headers=REDDIT_HEADERS, timeout=15) as client:
        try:
            response = await client.get(REDDIT_SEARCH_URL, params=params)
            if response.status_code != 200:
                logger.warning("Reddit search returned %s for term: %s", response.status_code, term)
                return []
            return response.json().get("data", {}).get("children", [])
        except httpx.RequestError as e:
            logger.error("Reddit request failed for term '%s': %s", term, e)
            return []


def is_obvious_skip(title: str, body: str) -> bool:
    title_lower = title.lower()
    if "[for hire]" in title_lower:
        return True
    if not body or body.strip() in ("", "[deleted]", "[removed]"):
        return True
    return False


async def process_term(term: str, recent_drafts: list[str], time_filter: str = "hour"):
    posts = await fetch_posts(term, time_filter)
    new_count = 0

    for wrapper in posts:
        post = wrapper.get("data", {})
        reddit_post_id = post.get("id")

        if not reddit_post_id:
            continue
        if post_exists(reddit_post_id):
            continue

        title = post.get("title", "")
        body = post.get("selftext", "")

        if is_obvious_skip(title, body):
            continue

        author = post.get("author", "")
        subreddit = post.get("subreddit", "")
        created_utc = post.get("created_utc", 0)
        posted_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

        result = await score_and_draft(title, body, recent_drafts)

        if result is None:
            logger.warning("Scoring failed for post %s — skipping", reddit_post_id)
            continue

        score = result["score"]
        reason = result["reason"]
        draft = result.get("draft", "")

        if score <= 2:
            continue

        post_data = {
            "reddit_post_id": reddit_post_id,
            "subreddit": subreddit,
            "title": title,
            "body": body,
            "author": author,
            "posted_at": posted_at,
            "score": score,
            "score_reason": reason,
            "status": "drafted" if draft else "new",
        }

        post_id = save_post(post_data)
        new_count += 1

        if score is not None:
            send_notification(
                post={**post_data, "reddit_post_id": reddit_post_id},
                score=score,
                reason=reason,
                draft=draft,
            )

        if draft:
            send_after = (
                datetime.now(tz=timezone.utc)
                + timedelta(minutes=randint(APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX))
            ).isoformat()

            save_message({
                "post_id": post_id,
                "draft": draft,
                "send_after": send_after,
                "status": "pending",
            })
            recent_drafts.insert(0, draft)
            if len(recent_drafts) > 5:
                recent_drafts.pop()

    if new_count:
        logger.info("Term '%s' — %d new post(s) saved", term, new_count)


async def run_watcher(time_filter: str = "hour"):
    logger.info("Watcher run started (filter: %s)", time_filter)
    recent_drafts = get_recent_drafts(limit=5)

    for i, term in enumerate(SEARCH_TERMS):
        await process_term(term, recent_drafts, time_filter)
        if i < len(SEARCH_TERMS) - 1:
            await asyncio.sleep(2)

    logger.info("Watcher run complete")


def run_cleanup():
    deleted = purge_old_posts()
    if deleted:
        logger.info("Cleanup: purged %d stale post(s)", deleted)
