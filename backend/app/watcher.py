import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from random import randint

import httpx

from app.config import (
    SEARCH_TERMS, SUBREDDIT_SOURCES, APPROVAL_WINDOW_MIN, APPROVAL_WINDOW_MAX,
    SEARCH_TERM_DELAY_SECONDS, SEARCH_BACKOFF_SECONDS,
)
from app.database import post_exists, save_post, save_message, get_recent_drafts, purge_old_posts, get_search_terms, get_setting, update_post_engagement
from app.scorer import score_and_draft
from app.notifications import send_notification

logger = logging.getLogger(__name__)

# Anonymous RSS read path (no login/API). A browser-like UA avoids some throttling.
REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/atom+xml",
}
REDDIT_SEARCH_RSS = "https://www.reddit.com/search.rss"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}

_last_run_at: str | None = None


def get_last_run_at() -> str | None:
    return _last_run_at


async def _fetch_rss(url: str, params: dict, label: str) -> list[dict]:
    """GET an anonymous Reddit Atom feed and parse it. No login/API/credentials.
    On a 429 (Reddit throttles anonymous reads) back off and return [] so the
    sweep stays gentle rather than hammering."""
    async with httpx.AsyncClient(headers=REDDIT_HEADERS, timeout=20, follow_redirects=True) as client:
        try:
            response = await client.get(url, params=params)
        except httpx.RequestError as e:
            logger.error("Reddit RSS request failed for %s: %s", label, e)
            return []
    if response.status_code == 429:
        logger.warning("Reddit RSS rate-limited (429) for %s — backing off %ss", label, SEARCH_BACKOFF_SECONDS)
        await asyncio.sleep(SEARCH_BACKOFF_SECONDS)
        return []
    if response.status_code != 200:
        logger.warning("Reddit RSS returned %s for %s", response.status_code, label)
        return []
    return _parse_atom(response.text)


async def fetch_posts(term: str, time_filter: str = "hour") -> list[dict]:
    """Newest posts matching `term` from Reddit's anonymous search RSS feed."""
    params = {"q": term, "sort": "new", "limit": 25, "type": "link"}
    if time_filter in ("hour", "day", "week", "month", "all"):
        params["t"] = time_filter
    return await _fetch_rss(REDDIT_SEARCH_RSS, params, f"term '{term}'")


async def fetch_subreddit_posts(sub: str) -> list[dict]:
    """Newest posts from r/<sub> via its anonymous new.rss feed — a dense source
    of real hiring posts the global search misses. The scorer filters seekers."""
    return await _fetch_rss(f"https://www.reddit.com/r/{sub}/new.rss", {"limit": 25}, f"r/{sub}")


def _parse_atom(xml_text: str) -> list[dict]:
    """Parse a Reddit search/subreddit Atom feed into normalised post dicts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Reddit RSS returned non-XML (throttle page?)")
        return []
    posts = []
    for entry in root.findall("a:entry", _ATOM):
        rid = (entry.findtext("a:id", "", _ATOM) or "").replace("t3_", "").strip()
        if not rid:
            continue
        author_el = entry.find("a:author/a:name", _ATOM)
        author = (author_el.text or "").replace("/u/", "").strip() if author_el is not None else ""
        cat_el = entry.find("a:category", _ATOM)
        subreddit = (cat_el.get("term") if cat_el is not None else "") or ""
        content = entry.findtext("a:content", "", _ATOM) or ""
        body = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", content))).strip()
        ts = entry.findtext("a:published", "", _ATOM) or entry.findtext("a:updated", "", _ATOM) or ""
        try:
            created_utc = datetime.fromisoformat(ts).timestamp() if ts else 0
        except ValueError:
            created_utc = 0
        posts.append({
            "id": rid,
            "title": (entry.findtext("a:title", "", _ATOM) or "").strip(),
            "selftext": body,
            "author": author,
            "subreddit": subreddit,
            "created_utc": created_utc,
            # RSS doesn't expose these; keep the pipeline's expected keys.
            "num_comments": 0,
            "score": 0,
            "over_18": False,
        })
    return posts


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
    "jobboards", "networkingjobs",
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

    # Automated job-board aggregator bots repost corporate listings as
    # "📢 [Company] [HIRING] a [Role]!" / "[HIRING] a [Role]! in [Loc]" — not
    # direct freelance hires, and there's no human author to DM.
    if title.strip().startswith("📢") or re.search(r"\[hiring\]\s+a\s+.+!", title_lower):
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


async def _process_posts(posts: list[dict], recent_drafts: list[str], seen_author_titles: set | None = None) -> tuple[int, int]:
    """Dedup, pre-filter, score, and persist a batch of fetched posts.
    Returns (opportunities_saved, rejects_saved)."""
    new_count = 0
    reject_count = 0

    for post in posts:
        reddit_post_id = post.get("id")

        if not reddit_post_id:
            continue
        if post.get("over_18", False):
            continue
        if await post_exists(reddit_post_id):
            await update_post_engagement(reddit_post_id, post.get("score", 0), post.get("num_comments", 0))
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
        posted_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)

        result = await score_and_draft(title, body, recent_drafts)

        if result is None:
            logger.warning("Scoring failed for post %s — skipping", reddit_post_id)
            continue

        score = result["score"]
        reason = result["reason"]
        draft = result.get("draft", "")

        if score <= 2:
            # Phase 11 — persist rejects for audit (no draft, message, or
            # notification). Lets us answer "did we miss a lead?" by scanning the
            # Rejected tab instead of re-running the LLM; auto-purged by the
            # 30-day retention sweep.
            await save_post({
                "reddit_post_id": reddit_post_id,
                "subreddit": subreddit,
                "title": title,
                "body": body,
                "author": author,
                "posted_at": posted_at,
                "score": score,
                "score_reason": reason,
                "status": "rejected",
                "num_comments": post.get("num_comments", 0),
                "reddit_upvotes": post.get("score", 0),
            })
            reject_count += 1
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

        post_id = await save_post(post_data)
        new_count += 1

        # SMTP is slow and blocking — keep it off the event loop. The enabled
        # check lives here (not in send_notification) so the thread never touches
        # the async DB.
        if await get_setting("notifications_enabled", "false") == "true":
            await asyncio.to_thread(
                send_notification,
                post={**post_data, "reddit_post_id": reddit_post_id},
                score=score,
                reason=reason,
                draft=draft,
            )

        if draft:
            window_min = int(await get_setting("approval_window_min", str(APPROVAL_WINDOW_MIN)))
            window_max = int(await get_setting("approval_window_max", str(APPROVAL_WINDOW_MAX)))
            send_after = datetime.now(tz=timezone.utc) + timedelta(
                minutes=randint(window_min, window_max)
            )

            await save_message({
                "post_id": post_id,
                "draft": draft,
                "send_after": send_after,
                "status": "pending",
            })
            recent_drafts.insert(0, draft)
            if len(recent_drafts) > 5:
                recent_drafts.pop()

    return new_count, reject_count


async def process_term(term: str, recent_drafts: list[str], time_filter: str = "hour", seen_author_titles: set | None = None) -> int:
    posts = await fetch_posts(term, time_filter)
    new_count, reject_count = await _process_posts(posts, recent_drafts, seen_author_titles)
    if new_count or reject_count:
        logger.info("Term '%s' — %d opportunity, %d rejected", term, new_count, reject_count)
    return new_count


async def process_subreddit(sub: str, recent_drafts: list[str], seen_author_titles: set | None = None) -> int:
    posts = await fetch_subreddit_posts(sub)
    new_count, reject_count = await _process_posts(posts, recent_drafts, seen_author_titles)
    if new_count or reject_count:
        logger.info("r/%s — %d opportunity, %d rejected", sub, new_count, reject_count)
    return new_count


async def search_term(term: str) -> int:
    recent_drafts = await get_recent_drafts(limit=5)
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
        recent_drafts = await get_recent_drafts(limit=5)
        seen_author_titles: set = set()

        db_terms = await get_search_terms()
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
                await asyncio.sleep(SEARCH_TERM_DELAY_SECONDS)

        # Poll targeted subreddit new-feeds too — denser in real gigs than the
        # global search. Same gentle pacing; the scorer filters seekers/noise.
        for sub in SUBREDDIT_SOURCES:
            await asyncio.sleep(SEARCH_TERM_DELAY_SECONDS)
            try:
                await process_subreddit(sub, recent_drafts, seen_author_titles)
            except Exception:
                logger.exception("r/%s failed — continuing with remaining sources", sub)

        global _last_run_at
        _last_run_at = datetime.now(tz=timezone.utc).isoformat()
        logger.info("Watcher run complete")


async def run_cleanup():
    deleted = await purge_old_posts()
    if deleted:
        logger.info("Cleanup: purged %d stale post(s)", deleted)
