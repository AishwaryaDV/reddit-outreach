#!/usr/bin/env python3
"""Grow the labeling pool with real posts from all search phrases.

Fetches each phrase from Reddit's anonymous search RSS (no login), paced with
429-backoff, and merges unique posts into evals/data/candidates.jsonl (skipping
anything already labeled in golden.jsonl). Safe to re-run — it only adds new
posts. Takes a while because anonymous search is throttled (~90s per phrase).

    cd backend && source venv/bin/activate && python scripts/fetch_candidates.py
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `app` imports when run directly

from app.config import SEARCH_TERMS, SEARCH_TERM_DELAY_SECONDS
from app.watcher import fetch_posts

DATA = Path(__file__).resolve().parent.parent / "evals" / "data"
CAND = DATA / "candidates.jsonl"
GOLDEN = DATA / "golden.jsonl"


def _load(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-terms", type=int, default=0, help="limit phrases (0 = all)")
    ap.add_argument("--time", default="week", help="hour|day|week|month|all")
    args = ap.parse_args()

    pool = _load(CAND)
    labeled = set(_load(GOLDEN))
    terms = list(SEARCH_TERMS)
    if args.max_terms:
        terms = terms[: args.max_terms]

    DATA.mkdir(parents=True, exist_ok=True)
    print(f"fetching {len(terms)} phrase(s), paced ~{SEARCH_TERM_DELAY_SECONDS}s "
          f"(pool starts at {len(pool)})")
    for i, term in enumerate(terms, 1):
        posts = await fetch_posts(term, args.time)
        added = 0
        for p in posts:
            if not p.get("title") or p["id"] in labeled or p["id"] in pool:
                continue
            pool[p["id"]] = {"id": p["id"], "title": p["title"],
                             "body": p["selftext"][:1500], "subreddit": p["subreddit"]}
            added += 1
        with open(CAND, "w") as f:  # write after each term so progress is saved
            for r in pool.values():
                f.write(json.dumps(r) + "\n")
        print(f"  [{i}/{len(terms)}] {term!r:40} +{added}  (pool={len(pool)})")
        if i < len(terms):
            await asyncio.sleep(SEARCH_TERM_DELAY_SECONDS)

    print(f"\ndone — {len(pool)} unlabeled candidates. Label them: python scripts/label.py")


if __name__ == "__main__":
    asyncio.run(main())
