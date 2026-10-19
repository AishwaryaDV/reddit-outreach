#!/usr/bin/env python3
"""Label real Reddit posts for the scorer golden set.

Reads unlabeled posts from evals/data/candidates.jsonl, shows each one, and
writes YOUR labels to evals/data/golden.jsonl. Resume-able: posts already in
golden.jsonl (by id) are skipped, so you can label in sittings.

    cd backend && source venv/bin/activate && python scripts/label.py

Your labels are the ground truth the scorer is measured against — only real
posts, only your judgment.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "evals" / "data"
CANDIDATES = DATA / "candidates.jsonl"
GOLDEN = DATA / "golden.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    cands = _read_jsonl(CANDIDATES)
    done_ids = {r["id"] for r in _read_jsonl(GOLDEN)}
    todo = [c for c in cands if c["id"] not in done_ids]
    if not todo:
        print("Nothing to label — all candidates are already in golden.jsonl.")
        return

    print(f"\n{len(todo)} to label ({len(done_ids)} already done).")
    print("Keys:  [o] opportunity   [n] not an opportunity   [s] skip   [q] save & quit\n")

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN, "a") as out:
        for i, c in enumerate(todo, 1):
            print("=" * 72)
            print(f"[{i}/{len(todo)}]  r/{c['subreddit']}")
            print(f"TITLE: {c['title']}")
            print(f"BODY : {c['body'][:700]}")
            print("-" * 72)

            choice = ""
            while choice not in ("o", "n", "s", "q"):
                choice = input("label [o/n/s/q]: ").strip().lower()
            if choice == "q":
                break
            if choice == "s":
                print()
                continue

            label = "opportunity" if choice == "o" else "not_opportunity"
            score = 0
            while not (1 <= score <= 10):
                raw = input("score 1-10: ").strip()
                score = int(raw) if raw.isdigit() else 0
            note = input("note (optional): ").strip()

            out.write(json.dumps({
                "id": c["id"], "title": c["title"], "body": c["body"],
                "subreddit": c["subreddit"], "human_label": label,
                "human_score": score, "notes": note,
            }) + "\n")
            out.flush()
            print("  saved.\n")

    total = len(_read_jsonl(GOLDEN))
    print(f"\nDone. golden.jsonl now has {total} labeled post(s).")


if __name__ == "__main__":
    main()
