import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from random import randint

import httpx

from app.config import SEARCH_TERMS, APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX
from app.database import post_exists, save_post, save_message, get_recent_drafts, purge_old_posts, get_search_terms
from app.scorer import score_and_draft
from app.notifications import send_notification

logger = logging.getLogger(__name__)

REDDIT_HEADERS = {"User-Agent": "reddit-outreach-personal-tool/1.0"}
REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"


async def fetch_posts(term: str, time_filter: str = "hour") -> list[dict]:
    params = {"q": term, "sort": "new", "t": time_filter, "limit": 50}
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


_URL_RE = re.compile(r"https?://\S+")

_JOB_SEEKER_PHRASES = [
    "looking for work", "looking for a job", "open to work",
    "available for work", "seeking work", "seeking opportunities",
    "portfolio review", "rate my portfolio", "just launched", "just finished",
    "hire me", "looking for advice", "looking for suggestion", "looking for suggestions",
]

_NO_PAY_PHRASES = [
    "revenue share", "rev share",
    "sweat equity", "equity only",
    "unpaid", "no budget", "no pay", "work for free", "pro bono",
    "volunteer",
    "student project", "school project", "class project", "uni project",
    "spec work",
]

_PLATFORM_BLOCKLIST = ["micro1", "mercor"]

_SUBREDDIT_BLOCKLIST = [
    "jobboards", "networkingjobs", "forhire",
]

_IRRELEVANT_STACKS = [
    "cobol", "mainframe", "jcl", "vsam", "cics", "ibm z/os",
    "electron", "electronjs",
]

_MICROTASK_PHRASES = [
    "typing speed", "upvote the post", "slots available", "hurry up",
]

_LOCATION_PHRASES = [
    "must be located in", "must be based in", "must live in",
    "us only", "usa only", "united states only", "us-based only",
    "must be in the us", "must be in the usa",
]

_ONSITE_PHRASES = [
    "onsite", "on-site", "on site", "in-person", "in person",
    "in office", "in-office", "must relocate", "office-based",
]


def is_obvious_skip(title: str, body: str, subreddit: str = "", author: str = "") -> bool:
    title_lower = title.lower()
    body_clean = (body or "").strip()
    body_lower = body_clean.lower()
    subreddit_lower = subreddit.lower()
    author_lower = author.lower()

    # Poster is offering services, not hiring
    if "[for hire]" in title_lower:
        return True

    # No content
    if not body_clean or body_clean in ("[deleted]", "[removed]"):
        return True

    # Too short to be a real hiring post
    if len(body_clean) < 150:
        return True

    # Short title paired with thin body — combined signal of a low-effort post
    if len(title.strip()) < 20 and len(body_clean) < 300:
        return True

    # Body is essentially just a URL with no real description
    body_without_urls = _URL_RE.sub("", body_clean).strip()
    if len(body_without_urls) < 50:
        return True

    # Job board subreddit posting scraped listings with a link and minimal text
    if "job" in subreddit_lower and len(body_without_urls) < 200:
        return True

    # Explicitly blocked subreddits
    if subreddit_lower in _SUBREDDIT_BLOCKLIST:
        return True

    # Poster is the job seeker, not the hirer
    if title_lower.startswith("[h]"):
        return True
    if any(phrase in title_lower for phrase in _JOB_SEEKER_PHRASES):
        return True

    # Blocked platforms (scrapers, low-signal job boards)
    combined = title_lower + " " + body_lower
    if any(platform in combined or platform == author_lower for platform in _PLATFORM_BLOCKLIST):
        return True

    # No-pay or scam signals in title or body
    if any(phrase in combined for phrase in _NO_PAY_PHRASES):
        return True

    # Location-restricted (geography-locked roles)
    if any(phrase in combined for phrase in _LOCATION_PHRASES):
        return True

    # Onsite / in-person only roles
    if any(phrase in combined for phrase in _ONSITE_PHRASES):
        return True

    # Irrelevant tech stacks (title only — safer than body to avoid false positives)
    if any(stack in title_lower for stack in _IRRELEVANT_STACKS):
        return True

    # Microtask / spam signals
    if any(phrase in combined for phrase in _MICROTASK_PHRASES):
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
        if post.get("over_18", False):
            continue
        if post_exists(reddit_post_id):
            continue

        title = post.get("title", "")
        body = post.get("selftext", "")
        author = post.get("author", "")
        subreddit = post.get("subreddit", "")

        if is_obvious_skip(title, body, subreddit, author):
            continue
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
            "num_comments": post.get("num_comments", 0),
            "reddit_upvotes": post.get("score", 0),
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

    db_terms = get_search_terms()
    active_terms = db_terms if db_terms else SEARCH_TERMS
    logger.info("Using %d search term(s) (%s)", len(active_terms), "from DB" if db_terms else "from config")

    for i, term in enumerate(active_terms):
        await process_term(term, recent_drafts, time_filter)
        if i < len(active_terms) - 1:
            await asyncio.sleep(2)

    logger.info("Watcher run complete")


def run_cleanup():
    deleted = purge_old_posts()
    if deleted:
        logger.info("Cleanup: purged %d stale post(s)", deleted)
