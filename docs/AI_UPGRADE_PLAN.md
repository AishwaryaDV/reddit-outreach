# AI Upgrade — Engineering Plan

**Created: 2026-10-17 | Branch: feat/ai-upgrade**

The working plan for turning reddit-outreach from a personal script into a measured,
testable LLM pipeline. Based on `docs/reddit-outreach-ai-upgrade-spec.pdf` (2026-10-11).
We work in **incremental phases, test each before moving on** — no fixed timeline.

**Model decision (locked):** Claude Agent SDK (Haiku, via Claude Code login, no API key) =
primary scorer/drafter. Gemini (Flash, free tier, `GEMINI_API_KEY`) = fallback + CI + draft judge.

---

## What changes, engineering-wise (before → after)

| Dimension | Today | After this plan |
|---|---|---|
| Model output | Free text, parsed with a 3-tier regex fallback | Pydantic schema, JSON-schema output, validated + retry-on-fail |
| Quality | Unmeasured (and currently a mock returning 7) | F1 / precision / recall / Spearman vs a hand-labeled golden set |
| Regressions | A prompt change can silently worsen scoring | CI eval gate fails the PR if F1 drops |
| Cost / latency | Invisible | Every call logged (tokens, $, ms, parse-ok) → `/metrics` page |
| Models | One, hardcoded, commented out | Primary + fallback behind one `llm_client` |
| Prompts | A Python string literal | Versioned files (`prompts/scorer/v1.md`, v2…) + changelog |
| Untrusted input | Reddit text goes straight into the prompt | Delimited as data + adversarial test posts that must score low |
| Draft quality | Never checked | LLM-as-judge (Gemini), calibrated against your hand scores |
| Reproducibility | Needs your Claude login just to run | Replay mode runs the whole thing with no accounts, no cost |
| Sending | Auto-send on, no dedup | Human-approval default; auto-send opt-in; never-DM-twice (done) |

The product (find dev gigs, draft DMs, review, send) is unchanged. What's new is the
**measurement, safety, and portability** around the LLM.

---

## Phases

Each phase lists: **goal · what we build · test · done-when · needs-from-you.**
Phases 1–8 are the AI upgrade. Phase 0 (ingestion) and Phase 9 (deploy/security) bracket them.

### Phase 0 — Reddit OAuth reads (BUG-0) · unblocks ingestion
- **Goal:** fix the 403; get fresh posts flowing again.
- **Build:** move `fetch_posts()` from raw httpx on `search.json` to authenticated reads
  (PRAW `reddit.subreddit("all").search(...)` or OAuth'd httpx on `oauth.reddit.com`).
- **Test:** watcher run returns real posts for the 10 search terms; no 403s.
- **Done when:** a live watcher run saves new posts to Supabase.
- **Needs from you:** register the Reddit script app; `REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD`
  in `.env`. *(Also pulls the ~100 fresh posts we want for the dataset — see Phase 2.)*

### Phase 1 — `llm_client.py` wrapper + replay + cost logging · the foundation
- **Goal:** one chokepoint for every model call, so everything after can be measured and swapped.
- **Build:**
  - `backend/app/llm_client.py` — backends `claude_sdk` (Agent SDK) and `gemini`; pipeline code
    never imports either SDK directly.
  - Fallback policy: try Claude → on timeout/error/quota, retry once → fall back to Gemini; record
    `backend` + `fell_back`.
  - `LLM_MODE=live` (default) vs `LLM_MODE=replay` (serves recorded responses from `evals/cache/`,
    calls no model).
  - `llm_calls` Supabase table + a helper that writes one row per call (see SQL below).
  - Add `google-genai` to `requirements.txt`.
- **Test:** score a handful of existing posts in live mode (Claude), force a failure and confirm
  Gemini fallback, run the same in replay mode with no network.
- **Done when:** `scorer.py` calls go through `llm_client`; `llm_calls` fills with real cost/latency.
- **Needs from you:** `GEMINI_API_KEY` (done ✅); run the `llm_calls` table SQL in Supabase.

### Phase 2 — Golden dataset + labeling tool
- **Goal:** ground truth to measure the scorer against.
- **Build:**
  - `scripts/export_for_labeling.py` — pulls ~200 posts across score buckets (oversampling the
    hard 3–6 range) + ~50 the pre-filters rejected → `evals/data/golden.jsonl`.
  - A `/label` dashboard page: one post at a time, opportunity/not + 1–10 + notes, keyboard-driven.
  - Freeze 40 as `evals/data/holdout.jsonl` (never used while tuning).
- **Dataset note:** the current Supabase posts are months old. We start with those **plus ~100
  fresh ones pulled after Phase 0**, so the set spans old and new.
- **Test:** export runs; `/label` writes valid JSONL rows.
- **Done when:** ~250 labeled (start with a ~50 sitting to get a first signal), holdout frozen.
- **Needs from you:** the labeling itself (the one part only you can do; do it in sittings of 50).

### Phase 3 — Eval harness + baseline numbers
- **Goal:** turn "is the scorer good?" into a number.
- **Build:** `evals/run_scorer_eval.py` → precision/recall/F1 at save threshold, confusion matrix,
  Spearman vs human score, mean abs error, parse-failure %, tokens/cost, p50/p95 latency; append a
  row to `evals/RESULTS.md`; cache responses by hash(prompt, model, post) so re-runs are free.
- **Test:** run on a 50-post dev subset; numbers reproduce from cache.
- **Done when:** a v1 baseline row is committed to `RESULTS.md`.

### Phase 4 — Structured outputs + prompt versioning + model comparison
- **Goal:** replace brittle text parsing; make prompts first-class; confirm Gemini as backup.
- **Build:**
  - `ScoreResult` Pydantic schema (`score`, `label`, `reasons[]`, `red_flags[]`,
    `budget_mentioned`, `draft?`) via the SDK's `output_format` / Gemini JSON-schema; validate,
    retry once on failure, log parse failures.
  - **Split scoring and drafting into two calls** (draft only for posts that pass → saves tokens).
  - Move prompts to `prompts/scorer/v1.md`, `v2.md` + `CHANGELOG.md`; record `prompt_version` +
    `model` on each saved post. v2 adds an explicit rubric + few-shot examples (from dev, never holdout).
  - Run the harness on v2 with Haiku and Gemini; table in `RESULTS.md`; write the fallback policy.
- **Test:** parse-failure rate drops; v2 vs v1 comparison committed.
- **Done when:** structured outputs live; v2 + comparison in `RESULTS.md`.

### Phase 5 — Threshold tuning + CI regression gate
- **Goal:** pick the save threshold on data; stop regressions automatically.
- **Build:** tabulate precision/recall for thresholds 2–7 (pick on dev, report final on holdout);
  `.github/workflows/eval.yml` — replay-mode eval on every push (free), + a live 30-post Gemini
  smoke run when `scorer.py`/`prompts/` change, failing if F1 drops >5 pts vs
  `evals/baselines/gemini_smoke.json`. Status badge in README.
- **Test:** open a PR with a deliberately bad prompt → CI goes red (screenshot it).
- **Done when:** holdout numbers reported once; CI gate demonstrated failing.

### Phase 6 — Draft judge + guardrails + human-approval default
- **Goal:** quality-check drafts; make sending safe by default.
- **Build:**
  - LLM-as-judge on Gemini (`prompts/judge/v1.md`, 1–5 on specificity/no-false-claims/length/
    tone/CTA); calibrate against 30 of your hand-scored drafts, report agreement, ship only if
    reasonable. Measure draft repetition via embedding similarity.
  - Code guardrails (not LLM): block drafts with non-allowlisted URLs, phone numbers, prices, or
    claims outside a `profile.yaml` of true facts. Prompt-injection defense: delimit post bodies as
    data; add ~10 adversarial posts to the golden set that must score low and leak nothing.
  - **Auto-send → opt-in, OFF by default** (`auto_send_enabled` in `app_settings`; keep the
    mechanism built in BUG-3). Keep the 20/day cap and the never-DM-twice guard (done).
- **Test:** injection posts score low; guardrails block a planted bad draft; judge agreement reported.
- **Done when:** judge calibrated + shipped; guardrails enforced; approval required by default.

### Phase 7 — `/metrics` dashboard
- **Goal:** see cost, latency, and the funnel.
- **Build:** `/metrics` page: calls+spend/day, p50/p95 per step, parse-failure rate, the funnel
  (fetched → pre-filtered → scored → saved → drafted → approved → sent), approve-rate by score
  bucket, fallback count. Log human edits to drafts (original vs final + edit distance). Quota
  guard: a daily LLM-call cap that pauses scoring + shows a banner.
- **Done when:** `/metrics` renders real data from `llm_calls`.

### Phase 8 — README + housekeeping
- **Build:** root README with one-line pitch, demo GIF, Mermaid architecture diagram, results
  table (from `RESULTS.md`), design tradeoffs, how-to-run + how-to-eval, limitations. Move `.docx`
  into `docs/`, anonymize usernames in `GOOD_POSTS.md`/`SAMPLE_POSTS.md`, add repo topics.
- **Done when:** a fresh clone can `make demo` in replay mode with no accounts.

### Phase 9 — Security hardening + deployment (BUG-14, self-host)
- **Build:** bearer-token auth on all non-health endpoints; Supabase RLS anon = SELECT only, route
  mutations through the backend; rate limiting. Then self-host on Ubuntu + nginx (see ROADMAP §6).
- **Done when:** deployed with auth, `DRY_RUN` set intentionally, watcher kept alive under systemd.

---

## `llm_calls` table (run in Supabase SQL editor at Phase 1)

```sql
create table if not exists llm_calls (
  id            uuid primary key default gen_random_uuid(),
  post_id       uuid references posts(id) on delete set null,
  step          text not null,              -- 'score' | 'draft' | 'judge'
  model         text not null,
  backend       text not null,              -- 'claude_sdk' | 'gemini'
  fell_back     boolean not null default false,
  prompt_version text,
  input_tokens  int,
  output_tokens int,
  cost_usd      numeric,
  latency_ms    int,
  parse_ok      boolean,
  error         text,
  created_at    timestamptz not null default now()
);
create index if not exists llm_calls_created_at_idx on llm_calls (created_at desc);
create index if not exists llm_calls_step_idx on llm_calls (step);
```

---

## Open bugs (2)
- **BUG-0** — Reddit public JSON 403 → ingestion dead. Fixed in Phase 0 (needs Reddit creds).
- **BUG-14** — no API auth + frontend writes via anon key. Fixed in Phase 9 (deploy).

## Don'ts (from the spec)
- No LangChain / heavy frameworks — plain SDK calls.
- Don't tune prompts on the holdout.
- Don't commit real Reddit usernames, API keys, or the Supabase service key.
- Don't remove the cheap pre-filters — the cost tradeoff is part of the story.
