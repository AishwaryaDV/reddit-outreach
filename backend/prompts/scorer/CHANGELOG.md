# Scorer prompt changelog

Each version is a `vN.md` file. The active version is `PROMPT_VERSION` in `app/scorer.py`
and is recorded on every call in the `llm_calls` table, so eval results can be tied to the
exact prompt that produced them.

## v1 (2026-10-19)
Baseline — extracted verbatim from the old inline `SYSTEM_PROMPT_TEMPLATE` in `scorer.py`.
1–10 rubric, 3-line message rules, anti-bot variation, free-text JSON output
(`{score, reason, draft}`). No behavioural change from the previous inline prompt — this
commit only moves it into a versioned file.
