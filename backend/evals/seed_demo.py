"""Seed the DB from local candidates for a live demo — no Reddit calls.

Clears posts + messages, then runs the REAL scoring pipeline (pre-filter ->
score_and_draft: triage/route -> score -> guardrails -> draft) over a slice of
candidates.jsonl and persists exactly like the watcher does (reject-audit for
score<=2, drafted + pending Message otherwise).

Demo-hardened: routes scoring to Gemini only (skips the slow Claude tier) and
wraps each post in a timeout so a slow model call can never stall the run.

Usage:  python -m evals.seed_demo [N]      (default N=30)
"""
import asyncio
import json
import random
import sys
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete

from app.db import get_session_factory
from app.models import Post, Message
from app.database import save_post, save_message, post_exists
from app.watcher import is_obvious_skip
from app.scorer import score_and_draft

from pathlib import Path
DATA = Path(__file__).parent / "data" / "candidates.jsonl"
PER_POST_TIMEOUT = 45


def _load(n: int) -> list[dict]:
    rows = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    random.seed(7)
    random.shuffle(rows)
    return rows[:n]


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    async with get_session_factory()() as s:
        await s.execute(delete(Message))
        await s.execute(delete(Post))
        await s.commit()
    print(f"cleared posts + messages; seeding up to {n} candidates (Gemini-only)...", flush=True)

    rows = _load(n)
    now = datetime.now(tz=timezone.utc)
    drafted = rejected = skipped = failed = 0
    recent_drafts: list[str] = []

    for i, r in enumerate(rows):
        rid = r["id"]
        title = r.get("title", "")
        body = r.get("body", "")
        subreddit = r.get("subreddit", "") or "forhire"
        author = f"redditor_{rid[:5]}"
        posted_at = now - timedelta(minutes=i * 7)

        if await post_exists(rid) or is_obvious_skip(title, body, subreddit, author):
            skipped += 1
            continue

        try:
            result = await asyncio.wait_for(
                score_and_draft(title, body, recent_drafts), timeout=PER_POST_TIMEOUT
            )
        except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001 — demo must never die
            failed += 1
            print(f"  [{i}] {title[:48]!r} -> failed ({type(e).__name__})", flush=True)
            continue

        if result is None:
            failed += 1
            continue

        score, reason, draft = result["score"], result["reason"], result.get("draft", "")
        base = {
            "reddit_post_id": rid, "subreddit": subreddit, "title": title, "body": body,
            "author": author, "posted_at": posted_at, "score": score, "score_reason": reason,
            "num_comments": random.randint(0, 14), "reddit_upvotes": random.randint(0, 60),
        }

        if score <= 2:
            await save_post({**base, "status": "rejected"})
            rejected += 1
            tag = "REJECT"
        else:
            post_id = await save_post({**base, "status": "drafted" if draft else "new"})
            if draft:
                await save_message({
                    "post_id": post_id, "draft": draft,
                    "send_after": now + timedelta(minutes=random.randint(2, 5)),
                    "status": "pending",
                })
                recent_drafts.insert(0, draft)
                recent_drafts[:] = recent_drafts[:5]
            drafted += 1
            tag = f"DRAFT s={score}"
        print(f"  [{i}] {tag:10} {title[:52]!r}", flush=True)

    print(f"\ndone: {drafted} drafted, {rejected} rejected, {skipped} pre-filtered, "
          f"{failed} failed", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
