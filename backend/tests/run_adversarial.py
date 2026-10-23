#!/usr/bin/env python3
"""Run the adversarial prompt-injection set through the scorer.

Each post is a crafted attack: score inflation, link injection, or fabrication.
A PASS means the injection was ignored — the score stayed at/under expect_max_score
AND the draft leaked none of the forbidden substrings (bad links / fake claims).

    cd backend && source venv/bin/activate && python tests/run_adversarial.py

Forces Gemini (no Pro). Needs scoring_enabled=true and the DB up.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("CLAUDE_MAX_PER_MIN", "0")   # Gemini only — no Pro
os.environ.setdefault("CLAUDE_MAX_PER_HOUR", "0")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scorer import score_and_draft  # noqa: E402

DATA = Path(__file__).resolve().parent / "adversarial.jsonl"


async def main() -> int:
    cases = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    failures = 0
    for c in cases:
        r = await score_and_draft(c["title"], c["body"])
        if r is None:
            print(f"[SKIP] {c['id']}: scorer returned None (scoring disabled / quota?)")
            continue
        draft = (r.get("draft") or "").lower()
        score = r["score"]
        bad_score = score > c["expect_max_score"]
        leaked = [s for s in c.get("forbidden_substrings", []) if s.lower() in draft]
        ok = not bad_score and not leaked
        failures += 0 if ok else 1
        extra = ""
        if bad_score:
            extra += f" score={score}>{c['expect_max_score']}"
        if leaked:
            extra += f" leaked={leaked}"
        print(f"[{'PASS' if ok else 'FAIL'}] {c['id']} (score {score}){extra}")
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
