"""Score the real saved leads and add them to the demo DB — no Reddit, no wipe.

Reads the post ids in evals/data/real_leads_ids.json (fetched from the owner's
saved posts via per-post RSS), scores each through the live pipeline
(score_and_draft), and persists: score>2 with a draft -> 'drafted' + pending
Message; score<=2 -> 'rejected' (audit). Existing posts are left untouched, so
these real leads layer on top of the already-seeded rejects.

Run with the working model:  GEMINI_MODEL=gemini-flash-lite-latest python -m evals.seed_leads
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Demo routing: score on Gemini (fast, no Pro burn). The real-fit leads would
# otherwise route to Claude, which is slow + rate-budgeted. Gemini drafts good
# posts fine; Claude quality is already verified separately.
import app.llm_client as _llm
async def _no_claude() -> bool:
    return False
_llm._claude_budget_available = _no_claude

from app.database import save_post, save_message, post_exists
from app.scorer import score_and_draft

DATA = Path(__file__).parent / "data"
PER_POST_TIMEOUT = 60  # Claude can be slow; give leads room


def _load() -> list[dict]:
    ids = json.loads((DATA / "real_leads_ids.json").read_text())
    by_id = {}
    for line in (DATA / "candidates.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            by_id[r["id"]] = r
    return [by_id[i] for i in ids if i in by_id]


async def main():
    leads = _load()
    now = datetime.now(tz=timezone.utc)
    drafted = rejected = skipped = 0
    print(f"scoring {len(leads)} real leads (no wipe)...", flush=True)

    for i, r in enumerate(leads):
        rid, title, body = r["id"], r.get("title", ""), r.get("body", "")
        if await post_exists(rid):
            skipped += 1
            continue
        try:
            result = await asyncio.wait_for(score_and_draft(title, body), timeout=PER_POST_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}] {title[:46]!r} -> failed ({type(e).__name__})", flush=True)
            continue
        if result is None:
            print(f"  [{i}] {title[:46]!r} -> no result", flush=True)
            continue

        score, reason, draft = result["score"], result["reason"], result.get("draft", "")
        base = {
            "reddit_post_id": rid, "subreddit": r.get("subreddit", ""), "title": title,
            "body": body, "author": f"redditor_{rid[:5]}", "posted_at": now - timedelta(hours=i + 1),
            "score": score, "score_reason": reason, "num_comments": 3 + i, "reddit_upvotes": 5 + 2 * i,
        }
        if score <= 2:
            await save_post({**base, "status": "rejected"})
            rejected += 1
            tag = "REJECT"
        else:
            pid = await save_post({**base, "status": "drafted" if draft else "new"})
            if draft:
                await save_message({
                    "post_id": pid, "draft": draft,
                    "send_after": now + timedelta(minutes=3), "status": "pending",
                })
            drafted += 1
            tag = f"DRAFT s={score}"
        print(f"  [{i}] {tag:10} r/{r.get('subreddit','')} {title[:48]!r}", flush=True)

    print(f"\ndone: {drafted} drafted, {rejected} rejected, {skipped} already-present", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
