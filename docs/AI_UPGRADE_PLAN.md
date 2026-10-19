# AI Upgrade — Engineering Plan

**Created: 2026-10-17 | Branch: feat/ai-upgrade**

The working plan for turning reddit-outreach from a personal script into a measured,
testable LLM pipeline. Based on `docs/reddit-outreach-ai-upgrade-spec.pdf` (2026-10-11).
We work in **incremental phases, test each before moving on** — no fixed timeline.

**Model decision (locked):** Claude Agent SDK (Haiku, via Claude Code login, no API key) =
primary scorer/drafter. Gemini (Flash, free tier, `GEMINI_API_KEY`) = fallback + CI + draft judge.

**Infra decision (locked 2026-10-17):** drop Supabase; self-host everything (DB, backend,
frontend) on one Ubuntu server, like the other apps. DB = **self-hosted PostgreSQL**, backend
access via **SQLAlchemy 2.0 async + Alembic**, frontend talks **only to the backend** (no DB
client), live feed via **react-query polling** (not Realtime). This is Phase 0.5 below and runs
before the AI phases, since everything after writes to the DB. It also structurally removes most
of BUG-14 (no more anon-key writes from the browser).

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
Phases 10–11 (ingestion recall + reject audit) were added after the Phase 7 metrics pass surfaced
a recall gap: the scorer is well-calibrated but the search feeds it ~0 real dev-hiring posts.

### Phase 0 — Reddit OAuth reads (BUG-0) · unblocks ingestion
- **Goal:** fix the 403; get fresh posts flowing again.
- **Build:** move `fetch_posts()` from raw httpx on `search.json` to authenticated reads
  (PRAW `reddit.subreddit("all").search(...)` or OAuth'd httpx on `oauth.reddit.com`).
- **Test:** watcher run returns real posts for the 10 search terms; no 403s.
- **Done when:** a live watcher run saves new posts to the DB.
- **Needs from you:** register the Reddit script app; `REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD`
  in `.env`. *(Also pulls the ~100 fresh posts we want for the dataset — see Phase 2.)*

### Phase 0.5 — De-Supabase: self-hosted Postgres + backend-only data access
- **Goal:** remove the Supabase dependency entirely; move to self-hosted Postgres; frontend talks
  only to the backend. **Decisions (2026-10-17):** SQLAlchemy 2.0 async + Alembic; react-query
  polling replaces Realtime; done before the AI phases. Mirror offroute's server layout.
- **Sub-steps (each testable on its own):**
  - **0.5a DB foundation** — local Postgres (docker-compose) for dev; SQLAlchemy async
    engine/session; models for `posts`, `messages`, `app_settings`, `search_terms` (+ `llm_calls`);
    Alembic init + baseline migration. Backend boots against local PG.
  - **0.5b Port the data layer** — rewrite `database.py` internals to SQLAlchemy, keeping the
    existing function names so the rest of the code barely changes; proper async session handling.
  - **0.5c Data re-seed** — `posts`/`messages` in Supabase are empty (the July data was purged by
    the 30-day retention cleanup during our test runs). So there's nothing to `pg_dump` — just
    re-seed the 14 `search_terms` (same as `config.SEARCH_TERMS`) + the 2 `app_settings`
    (`daily_dm_cap=20`, `notifications_enabled=false`) into local Postgres. A few lines, no script.
  - **0.5d Backend endpoints for all frontend data** — posts feed (filters/pagination/delete),
    message approve/cancel, search-terms CRUD, tracker outcome update. (These replace the
    frontend's direct DB writes.)
  - **0.5e Frontend cutover** — remove `@supabase/supabase-js`; replace every `supabase.from()`
    call with `fetch` to the new endpoints; Realtime → react-query polling; drop `VITE_SUPABASE_*`.
  - **0.5f Cleanup** — remove supabase deps; update `.env.example` (`DATABASE_URL`) + README;
    verify the whole app end-to-end on local Postgres.
- **Test:** full app runs locally with **zero** Supabase; existing data present; feed / review /
  queue / tracker / settings all work.
- **Done when:** no `supabase` imports remain; app runs on self-hosted Postgres; BUG-14's
  browser-direct-write path is gone.
- **Needs from you:** Docker (or a local Postgres) for dev; Postgres on the server later.

### Phase 1 — `llm_client.py` wrapper + replay + cost logging · the foundation
- **Goal:** one chokepoint for every model call, so everything after can be measured and swapped.
- **Build:**
  - `backend/app/llm_client.py` — backends `claude_sdk` (Agent SDK) and `gemini`; pipeline code
    never imports either SDK directly.
  - Fallback policy: try Claude → on timeout/error/quota, retry once → fall back to Gemini; record
    `backend` + `fell_back`.
  - `LLM_MODE=live` (default) vs `LLM_MODE=replay` (serves recorded responses from `evals/cache/`,
    calls no model).
  - `llm_calls` table (added as an Alembic migration on the self-hosted Postgres — see schema
    below) + a helper that writes one row per call.
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
- **Dataset note:** the old Supabase posts are gone (empty tables — purged by retention). The
  golden set is built **entirely from fresh posts pulled after Phase 0**, so registering the
  Reddit app gates the labeling work.
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
- **Note:** Phase 0.5 already removes the anon-key / direct-browser-write risk (frontend only
  talks to the backend now), so most of BUG-14 is handled structurally. What's left here:
- **Build:** bearer-token auth on all non-health endpoints + rate limiting.
- **Deploy (mirror offroute's `docs/new-server-setup.md`):**
  - `apt install nginx postgresql postgresql-contrib python3-venv certbot python3-certbot-nginx`.
  - Postgres **local on the server**: `CREATE DATABASE reddit_outreach; CREATE USER ...;`
    `DATABASE_URL=postgresql+asyncpg://...@localhost:5432/reddit_outreach` (+ `_SYNC` psycopg2 for Alembic).
  - Backend: `venv` + `pip install -r requirements.txt`, `alembic upgrade head`, **systemd**
    `reddit-api.service` running `uvicorn app.main:app --host 127.0.0.1 --port 8000` (the APScheduler
    watcher lives in this process, so systemd keeps it alive).
  - Frontend (Vite SPA — simpler than offroute's Next.js): `npm run build` → nginx serves `dist/`
    statically. No web service needed.
  - **nginx** on one domain `reddit.aishwaryadv.space`: `/api/` → `127.0.0.1:8000`, `/` → `dist/`;
    `certbot --nginx` for SSL.
  - Claude: `claude auth login` as the server user (no API key); Gemini fallback covers lapses.
  - Optional: GitHub deploy webhook → `git pull` + `pip install` + `alembic upgrade head` + restart.
- **Done when:** deployed with auth, `DRY_RUN` set intentionally, watcher alive under systemd.

### Phase 10 — Ingestion recall: widen the net, trust the scorer
- **Why:** a calibration pass (13 real posts via Gemini) and a scan of 66 fetched candidates found
  **zero** clean "employer hiring a web/fullstack dev" posts — all noise, showcases, job-seekers,
  or non-dev `[Hiring]`. The scorer rejected every one *correctly*. So "catching nothing" is a
  **recall** problem (the search feeds it ~0 real gigs), not a scorer problem.
- **Root causes:** (1) global `search.rss` does loose full-text matching → drags in unrelated subs
  while good niche posts don't rank; (2) `_SUBREDDIT_BLOCKLIST` blocks `forhire` — a *main* source
  of real `[Hiring]` dev gigs — to avoid seekers, but the scorer now filters seekers better than a
  crude sub blocklist (proven: every seeker in calibration → score 1).
- **Build:**
  - Drop `forhire` (re-evaluate `jobboards`/`networkingjobs`) from the blocklist; let the scorer
    filter seekers instead of pre-filtering by subreddit.
  - Poll targeted subreddit `new` feeds (higher gig density than global search): `/r/<sub>/new.rss`
    for forhire, jobbit, freelance_forhire, remotejs, hiring, slavelabour, plus stack/location subs —
    merged + deduped (by post id) with the existing global `search.rss`.
  - Flair-aware ranking: prefer `[Hiring]`/`[Task]`; treat `[For Hire]` as a seeker signal.
  - Tune/expand phrases (wordpress/shopify/webflow/next.js developer needed, "looking to hire",
    "paid gig", "contract developer").
- **Done when:** a watcher run surfaces real employer-hiring-a-dev posts scoring ≥ 3 over a window,
  and the funnel shows non-zero saved. (Phase 11's reject log is the measurement tool for this.)

### Phase 11 — Persist rejected posts (recall audit)
- **Why:** the watcher `continue`s on score ≤ 2 and **discards the score**, so "did we miss a lead?"
  is unanswerable — it already bit us (the 22 rejected scores were unrecoverable).
- **Build:** save every scored post, including ≤ 2, as status `rejected` (store score + label + top
  reason); never notify/draft/send for rejects. Auto-purged by the existing 30-day retention. Add a
  **Rejected** filter in the Feed + surface the reject score-distribution in `/metrics`, so false
  negatives are visible without re-running the LLM.
- **Done when:** every post the watcher scores is visible somewhere; you can scan rejects for
  mis-scored leads at a glance.

---

## `llm_calls` table (Alembic migration at Phase 1; schema reference)

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
- **BUG-14** — no API auth + frontend writes via anon key. Direct-write path removed in Phase 0.5;
  remaining backend auth + rate limiting in Phase 9 (deploy).

## Don'ts (from the spec)
- No LangChain / heavy frameworks — plain SDK calls.
- Don't tune prompts on the holdout.
- Don't commit real Reddit usernames, API keys, or DB credentials.
- Don't remove the cheap pre-filters — the cost tradeoff is part of the story.
