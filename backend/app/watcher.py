import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from random import randint

import httpx

from app.config import SEARCH_TERMS, APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX
from app.database import post_exists, save_post, save_message, get_recent_drafts, purge_old_posts, get_search_terms, get_setting
from app.scorer import score_and_draft
from app.notifications import send_notification

logger = logging.getLogger(__name__)

REDDIT_HEADERS = {"User-Agent": "reddit-outreach-personal-tool/1.0"}
REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"

_last_run_at: str | None = None


def get_last_run_at() -> str | None:
    return _last_run_at


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
        except ValueError:
            # Reddit occasionally returns HTML error pages with status 200
            logger.warning("Reddit returned non-JSON response for term: %s", term)
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

# These alone are strong enough — unambiguous hiring/tech role terms.
_TITLE_DIRECT_SIGNALS = [
    "hire", "hiring", "hired",
    "developer", "engineer", "programmer", "coder",
    "freelan",
    "web dev", "fullstack", "full stack", "full-stack",
    "frontend", "front-end", "backend", "back-end",
    "web app",
]

# These intent phrases are too broad alone ("looking for a pet") but valid when
# paired with a tech term in the same title ("looking for a react developer").
_TITLE_INTENT_PHRASES = [
    "looking for", "need a", "need an", "need someone",
    "seeking", "wanted", "want a", "want an",
]

_TITLE_TECH_TERMS = [
    "developer", "engineer", "programmer", "coder", "dev",
    "web", "app", "build", "fullstack", "react", "node",
    "frontend", "backend", "mvp", "website",
]

# Title-level hard stops — co-founder posts are not hiring posts.
_TITLE_BLOCKLIST = [
    "co-founder", "cofounder", "co founder",
]


def _title_has_signal(title_lower: str) -> bool:
    if any(s in title_lower for s in _TITLE_DIRECT_SIGNALS):
        return True
    # Intent phrase + tech term must both appear
    if any(p in title_lower for p in _TITLE_INTENT_PHRASES):
        return any(t in title_lower for t in _TITLE_TECH_TERMS)
    return False


def is_obvious_skip(title: str, body: str, subreddit: str = "", author: str = "") -> bool:
    title_lower = title.lower()
    body_clean = (body or "").strip()
    body_lower = body_clean.lower()
    subreddit_lower = subreddit.lower()
    author_lower = author.lower()

    # Title must have a hiring signal — Reddit's fuzzy search returns posts where
    # terms appear anywhere in the body, so random posts slip through without this.
    if not _title_has_signal(title_lower):
        return True

    # Co-founder posts are equity arrangements, not dev hires
    if any(phrase in title_lower for phrase in _TITLE_BLOCKLIST):
        return True

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


async def process_term(term: str, recent_drafts: list[str], time_filter: str = "hour", seen_author_titles: set | None = None):
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

        # Deduplicate cross-posts: same author posting the same title to many subreddits
        if seen_author_titles is not None:
            fingerprint = f"{author.lower()}::{title.lower()[:80]}"
            if fingerprint in seen_author_titles:
                continue
            seen_author_titles.add(fingerprint)

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

        # SMTP is slow and blocking — keep it off the event loop
        await asyncio.to_thread(
            send_notification,
            post={**post_data, "reddit_post_id": reddit_post_id},
            score=score,
            reason=reason,
            draft=draft,
        )

        if draft:
            window_min = int(get_setting("approval_window_min", str(APPROVAL_WINDOW_MIN)))
            window_max = int(get_setting("approval_window_max", str(APPROVAL_WINDOW_MAX)))
            send_after = (
                datetime.now(tz=timezone.utc)
                + timedelta(minutes=randint(window_min, window_max))
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
    return new_count


async def search_term(term: str) -> int:
    recent_drafts = get_recent_drafts(limit=5)
    seen: set = set()
    count = await process_term(term, recent_drafts, "day", seen)
    logger.info("Live search '%s' — %d new post(s) saved", term, count or 0)
    return count or 0


_watcher_lock = asyncio.Lock()


async def run_watcher(time_filter: str = "hour"):
    # Startup task, scheduler ticks, /watcher/run and /watcher/backfill can all
    # fire this — overlapping runs race the post_exists/save_post dedup check.
    if _watcher_lock.locked():
        logger.info("Watcher already running — skipping this trigger")
        return

    async with _watcher_lock:
        logger.info("Watcher run started (filter: %s)", time_filter)
        recent_drafts = get_recent_drafts(limit=5)
        seen_author_titles: set = set()

        db_terms = get_search_terms()
        if db_terms is None:
            active_terms = SEARCH_TERMS
            logger.info("Using %d search term(s) from config (DB unavailable)", len(active_terms))
        elif not db_terms:
            logger.info("All search terms disabled in Settings — skipping run")
            return
        else:
            active_terms = db_terms
            logger.info("Using %d search term(s) from DB", len(active_terms))

        for i, term in enumerate(active_terms):
            try:
                await process_term(term, recent_drafts, time_filter, seen_author_titles)
            except Exception:
                logger.exception("Term '%s' failed — continuing with remaining terms", term)
            if i < len(active_terms) - 1:
                await asyncio.sleep(2)

        global _last_run_at
        _last_run_at = datetime.now(tz=timezone.utc).isoformat()
        logger.info("Watcher run complete")


def run_cleanup():
    deleted = purge_old_posts()
    if deleted:
        logger.info("Cleanup: purged %d stale post(s)", deleted)
