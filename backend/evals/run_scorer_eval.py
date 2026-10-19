#!/usr/bin/env python3
"""Run the scorer over the golden set and report quality + cost metrics.

Answers "how often does the scorer agree with your labels?" with a number
(F1, Spearman, etc.). Forces Gemini (never Claude) by default so eval runs
never touch your Pro subscription.

    cd backend && source venv/bin/activate && python evals/run_scorer_eval.py
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# Protect the Pro subscription: eval runs go to Gemini, not Claude, unless --use-claude.
if "--use-claude" not in sys.argv:
    os.environ.setdefault("CLAUDE_MAX_PER_MIN", "0")
    os.environ.setdefault("CLAUDE_MAX_PER_HOUR", "0")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import get_session_factory  # noqa: E402
from app.models import LLMCall  # noqa: E402
from app.scorer import PROMPT_VERSION, score_and_draft  # noqa: E402

EVALS = Path(__file__).resolve().parent
GOLDEN = EVALS / "data" / "golden.jsonl"
RESULTS_MD = EVALS / "RESULTS.md"
RESULTS_DIR = EVALS / "results"
SAVE_THRESHOLD = 3  # score >= 3 => predicted "opportunity" (shown in the dashboard)

_HEADER = (
    "| run | prompt | backend | n | F1 | prec | recall | acc | Spearman | MAE | parse-fail | cost | p50/p95 |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
)


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _spearman(xs: list[float], ys: list[float]):
    n = len(xs)
    if n < 2:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    vx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    vy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return round(cov / (vx * vy), 3) if vx and vy else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between calls (pace Gemini)")
    ap.add_argument("--use-claude", action="store_true", help="allow Claude (uses Pro quota!)")
    args = ap.parse_args()

    rows = _load(GOLDEN)
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("No labeled posts in evals/data/golden.jsonl yet — label some first (scripts/label.py).")
        return

    run_start = datetime.now(tz=timezone.utc)
    print(f"running scorer over {len(rows)} labeled post(s) (prompt {PROMPT_VERSION})...")
    results = []
    for i, r in enumerate(rows, 1):
        out = await score_and_draft(r["title"], r["body"], [])
        model_score = out["score"] if out else None
        results.append({
            "id": r["id"], "human_label": r["human_label"],
            "human_score": r.get("human_score"), "model_score": model_score,
        })
        print(f"  [{i}/{len(rows)}] human={r['human_label']}/{r.get('human_score')} model={model_score}")
        await asyncio.sleep(args.delay)

    tp = fp = tn = fn = parse_fail = 0
    pairs, abs_err = [], []
    for r in results:
        human_opp = r["human_label"] == "opportunity"
        if r["model_score"] is None:
            parse_fail += 1
            pred_opp = False  # failed score => post dropped => not shown
        else:
            pred_opp = r["model_score"] >= SAVE_THRESHOLD
            if r["human_score"] is not None:
                pairs.append((r["model_score"], r["human_score"]))
                abs_err.append(abs(r["model_score"] - r["human_score"]))
        if human_opp and pred_opp:
            tp += 1
        elif not human_opp and pred_opp:
            fp += 1
        elif not human_opp and not pred_opp:
            tn += 1
        else:
            fn += 1

    n = len(results)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / n
    spearman = _spearman([p[0] for p in pairs], [p[1] for p in pairs])
    mae = round(statistics.mean(abs_err), 2) if abs_err else None

    async with get_session_factory()() as s:
        calls = (await s.execute(
            select(LLMCall).where(LLMCall.step == "score", LLMCall.created_at >= run_start)
        )).scalars().all()
    cost = round(sum(float(c.cost_usd or 0) for c in calls), 4)
    in_tok = sum(c.input_tokens or 0 for c in calls)
    out_tok = sum(c.output_tokens or 0 for c in calls)
    lats = sorted(c.latency_ms for c in calls if c.latency_ms)
    p50 = lats[len(lats) // 2] if lats else None
    p95 = lats[min(int(len(lats) * 0.95), len(lats) - 1)] if lats else None
    backends: dict[str, int] = {}
    for c in calls:
        backends[c.backend] = backends.get(c.backend, 0) + 1

    ts = run_start.strftime("%Y-%m-%d %H:%M")
    row = (f"| {ts} | {PROMPT_VERSION} | {'/'.join(f'{k}:{v}' for k, v in backends.items()) or '-'} | {n} | "
           f"{f1:.2f} | {precision:.2f} | {recall:.2f} | {accuracy:.2f} | {spearman} | {mae} | "
           f"{parse_fail / n * 100:.0f}% | ${cost} | {p50}/{p95}ms |")

    print("\n" + _HEADER)
    print(row)
    print(f"\nconfusion: TP={tp} FP={fp} TN={tn} FN={fn} | tokens in/out = {in_tok}/{out_tok}")

    if not RESULTS_MD.exists():
        RESULTS_MD.write_text(
            "# Scorer eval results\n\nPositive class = `opportunity`; predicted when score >= 3. "
            "Runs forced to Gemini unless noted.\n\n" + _HEADER + "\n"
        )
    with open(RESULTS_MD, "a") as f:
        f.write(row + "\n")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_json = RESULTS_DIR / f"{run_start.strftime('%Y%m%dT%H%M%S')}_{PROMPT_VERSION}.json"
    out_json.write_text(json.dumps({
        "run": ts, "prompt": PROMPT_VERSION, "n": n, "f1": round(f1, 3),
        "precision": round(precision, 3), "recall": round(recall, 3), "accuracy": round(accuracy, 3),
        "spearman": spearman, "mae": mae, "parse_fail_pct": round(parse_fail / n * 100, 1),
        "cost_usd": cost, "p50_ms": p50, "p95_ms": p95,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}, "backends": backends,
        "results": results,
    }, indent=2))
    print(f"\nappended to {RESULTS_MD.name}; full results -> {out_json.relative_to(EVALS.parent)}")


if __name__ == "__main__":
    asyncio.run(main())
