# Scorer prompt changelog

Each version is a `vN.md` file. The active version is `PROMPT_VERSION` in `app/scorer.py`
and is recorded on every call in the `llm_calls` table, so eval results can be tied to the
exact prompt that produced them.

## v1 (2026-10-19)
Baseline rubric (1–10), 3-line message rules, anti-bot variation. Output is the structured
`ScoreResult` schema (`score, label, reasons, red_flags, budget_mentioned, draft`), enforced
natively on Gemini via `response_schema` and validated with Pydantic on both backends (retry
once on a validation failure). (Started the same day as free-text `{score, reason, draft}`;
moved to the structured schema.)
