# Model Observations

Real behaviour we recorded while running the scoring pipeline on live Reddit
leads. This is the evidence behind dropping Gemini as the scoring backend in
favour of Claude (SDK now, Anthropic/OpenAI API keys later).

## TL;DR

Gemini's cheap tier (`gemini-flash-lite-latest`) **over-rejects legitimate
leads** — it dismisses real, well-scoped hiring posts that Claude correctly
scores high and drafts for. On the same posts, same prompt, same pipeline,
Claude's judgment matched a human's; Gemini's did not. Plus two operational
problems (a hanging model and daily quota 429s). So the scoring backend is
moving to Claude.

## The dismissal evidence

Same posts, same system prompt, same `score_and_draft` pipeline — only the
backend differs. Score is 1–10; a draft is only produced for a real fit.

| Lead (real, fetched from saved posts) | Gemini flash-lite | Claude Haiku |
|---|---|---|
| `[HIRING] Python Full Stack Developer \| Worldwide Remote` (FastAPI + React) | **rejected** (score ≤ 2, no draft) | **score 9, drafted** |
| `Senior Full-Stack Developer for SaaS Platform` (has an apply form + budget) | — | **score 8, drafted** |
| `[Hiring] Python Developer (Data/Automation) \| Remote` | **score 3, draft withheld** | **score 8, drafted** |
| `Remote Python Developer` (FastAPI + Postgres) | score 6, drafted | (not re-run) |

Four genuinely strong, on-profile leads. Gemini drafted **one**; Claude drafted
**all it saw**, with higher, better-calibrated scores.

### Honest counter-example (not everything is Gemini's fault)

`[Hiring] Full-Stack Developer | TaxCalc | B2B` — a job-board repost with the
real scope behind an external link and no direct hiring contact — was scored
**1 by both Gemini and Claude**. When a lead is genuinely weak, the models
agree. The divergence above is specifically about **real, reachable, on-profile
leads that Gemini wrongly dismisses.**

## Operational issues with Gemini

- **Hanging model:** `gemini-flash-latest` (our former primary) stopped
  responding mid-request server-side. With no per-call timeout it stalled the
  whole pipeline indefinitely instead of failing over. (Fixed separately with a
  `GEMINI_TIMEOUT_SECONDS` cap + failover — but it's a reliability smell.)
- **Daily quota 429s:** `RESOURCE_EXHAUSTED` on the free tier mid-run, pausing
  scoring unpredictably.

## Decision

- **Now:** Claude via the subscription SDK (keyless) is the single scoring
  backend. Judicious usage; swap out when subscription limits are hit.
- **Next:** make the backend pluggable behind a user-supplied **Anthropic** or
  **OpenAI** API key (usage-billed), so anyone running the tool brings their own
  model. Gemini removed.

## Caveats

- Small sample (a handful of leads), single run, one Gemini tier
  (`flash-lite`). Not a benchmark — a field observation that drove a decision.
- The over-rejection may be partly a cheap-tier effect; a larger Gemini model
  might do better, but it's moot since we're consolidating on Claude/OpenAI.
