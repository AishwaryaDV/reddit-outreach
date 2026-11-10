# Evals

Golden-dataset evaluation of the scorer — turns "is the scorer any good?" into a number.

## The flow

1. **Get real posts.** Run the watcher for a while so it ingests real posts, then
   `python scripts/export_for_labeling.py` pulls a sample (oversampling the hard 3–6
   score range) into `data/candidates.jsonl`. (You can also seed candidates from a
   direct search fetch.)
2. **Label them** — `python scripts/label.py` shows each real post and you mark it
   `opportunity` / `not_opportunity` + a 1–10 score. Writes `data/golden.jsonl`.
   Resume-able across sittings.
3. **Measure** — (next) `evals/run_scorer_eval.py` runs the scorer over the golden set
   and reports precision/recall/F1 at the save threshold, Spearman vs your scores,
   mean abs error, parse-failure %, and cost/latency into `RESULTS.md`.
4. Freeze ~40 posts as `data/holdout.jsonl` — never looked at while tuning prompts.

## Rules

- **Real posts only, your labels only.** The golden labels are *your* judgment — the
  ground truth. Never put made-up posts in here; they'd produce meaningless metrics.
- `data/candidates.jsonl` is a regenerable intermediate (gitignored). `data/golden.jsonl`
  and `data/holdout.jsonl` are the committed, curated sets.
