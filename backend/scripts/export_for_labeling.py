#!/usr/bin/env python3
"""Export posts from the DB into evals/data/candidates.jsonl for labeling.

Samples across score buckets, oversampling the hard middle (scores 3-6) where
the model is least certain. Run the watcher for a while first so there are real
posts to export, then label with scripts/label.py.

    cd backend && source venv/bin/activate && python scripts/export_for_labeling.py --limit 200
"""
import argparse
import asyncio
import json
import random
from pathlib import Path

from sqlalchemy import select

from app.db import get_session_factory
from app.models import Post

OUT = Path(__file__).resolve().parent.parent / "evals" / "data" / "candidates.jsonl"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    async with get_session_factory()() as session:
        posts = (await session.execute(select(Post))).scalars().all()
    if not posts:
        print("No posts in the DB yet — run the watcher to accumulate some, then re-run.")
        return

    buckets = {"low": [], "mid": [], "high": []}
    for p in posts:
        sc = p.score or 0
        key = "mid" if 3 <= sc <= 6 else ("high" if sc > 6 else "low")
        buckets[key].append(p)
    for b in buckets.values():
        random.shuffle(b)

    # Oversample the hard middle; include some high and low for balance.
    picked = (
        buckets["mid"][: args.limit // 2]
        + buckets["high"][: args.limit // 4]
        + buckets["low"][: args.limit // 4]
    )[: args.limit]

    rows = [
        {"id": p.reddit_post_id, "title": p.title or "", "body": (p.body or "")[:1500],
         "subreddit": p.subreddit or ""}
        for p in picked
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"exported {len(rows)} posts -> {OUT}  "
          f"(buckets: mid={len(buckets['mid'])} high={len(buckets['high'])} low={len(buckets['low'])})")


if __name__ == "__main__":
    asyncio.run(main())
