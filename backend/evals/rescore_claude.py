"""Re-score a few strong leads on CLAUDE (quality tier) and upsert into the DB.

For the given reddit ids: delete any existing row, score through the live
pipeline with Claude enabled (budget blocks intact), and persist the result
(drafted + Message / rejected / new). Judicious — only the handful passed in.

Run:  GEMINI_MODEL=gemini-flash-lite-latest python -m evals.rescore_claude
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from app.db import get_session_factory
from app.models import Post, Message
from app.database import save_post, save_message
from app.scorer import score_and_draft

DATA = Path(__file__).parent / "data"
TARGETS = ["1xr8q3u", "1xpxlme", "1xqqhpf"]   # SaaS(form), Python Full Stack, Data/Automation
TIMEOUT = 150   # Claude SDK can be slow


def _load() -> dict:
    by_id = {}
    for line in (DATA / "candidates.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            by_id[r["id"]] = r
    return by_id


async def main():
    by_id = _load()
    now = datetime.now(tz=timezone.utc)

    # Clear any existing rows for the targets so we insert fresh.
    async with get_session_factory()() as s:
        ids = (await s.execute(select(Post.id).where(Post.reddit_post_id.in_(TARGETS)))).scalars().all()
        if ids:
            await s.execute(delete(Message).where(Message.post_id.in_(ids)))
            await s.execute(delete(Post).where(Post.id.in_(ids)))
            await s.commit()

    drafted = rejected = other = 0
    for i, rid in enumerate(TARGETS):
        r = by_id.get(rid)
        if not r:
            print(f"  {rid}: not in candidates — skip", flush=True)
            continue
        title, body = r.get("title", ""), r.get("body", "")
        try:
            result = await asyncio.wait_for(score_and_draft(title, body), timeout=TIMEOUT)
        except Exception as e:  # noqa: BLE001
            print(f"  {rid} {title[:40]!r} -> failed ({type(e).__name__})", flush=True)
            continue
        if result is None:
            print(f"  {rid} -> no result", flush=True)
            continue
        score, reason, draft = result["score"], result["reason"], result.get("draft", "")
        base = {
            "reddit_post_id": rid, "subreddit": r.get("subreddit", ""), "title": title,
            "body": body, "author": f"redditor_{rid[:5]}", "posted_at": now - timedelta(hours=i + 1),
            "score": score, "score_reason": reason, "num_comments": 4 + i, "reddit_upvotes": 8 + 3 * i,
        }
        if score <= 2:
            await save_post({**base, "status": "rejected"}); rejected += 1; tag = "REJECT"
        elif draft:
            pid = await save_post({**base, "status": "drafted"})
            await save_message({"post_id": pid, "draft": draft,
                                "send_after": now + timedelta(minutes=3), "status": "pending"})
            drafted += 1; tag = f"DRAFT s={score}"
        else:
            await save_post({**base, "status": "new"}); other += 1; tag = f"NEW s={score} (no draft)"
        print(f"  {rid} | {tag:18} r/{r.get('subreddit','')} {title[:42]!r}", flush=True)

    print(f"\ndone: {drafted} drafted, {rejected} rejected, {other} new", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
