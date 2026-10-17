# Project Status — What's Done

**Last audited: 2026-10-14 | Branch: version1**

> This file was re-audited against live code on 2026-10-14. The previous version
> (July 7) predated the July 11–16 bug-fix sprint and listed ~15 bugs that are now
> fixed. Treat this as the current source of truth; see BUGS.md for what's still open.

---

## Quick state

| Area | State |
|---|---|
| Backend (FastAPI) | ✅ Runs locally on :8000, DB connected |
| Frontend (React/Vite) | ✅ Runs locally on :5173 |
| Supabase | ✅ Live (auto-pauses after ~7 days idle — resume if DNS goes NXDOMAIN) |
| Reddit ingestion | ❌ **Blocked** — public `search.json` now returns 403 (needs OAuth/PRAW) |
| Scorer | ⚠️ MOCK (returns 7 for everything); real Haiku scorer disabled |
| Sending | ⚠️ Dry-run only (`DRY_RUN=true`); auto-send of pending messages not wired (BUG-3) |
| Auth / security | ❌ No auth on any endpoint; frontend writes via anon key (fine locally, not for prod) |
| Deployment | ⬜ Not started — will **self-host** (Ubuntu + nginx), same as portfolio/offroute |

---

## Phase 1 — Reddit Watcher + AI Scoring ✅ (ingestion now blocked by Reddit 403)

Everything is built and wired. The watcher runs on a 10-minute APScheduler interval, cycles
through search terms (from the `search_terms` table, falling back to config), fetches up to 50
posts per term, and feeds each through the filter pipeline.

**⚠️ 2026-10 regression:** Reddit now returns **403** on unauthenticated `www.reddit.com/search.json`
requests (confirmed with a direct curl, not just our app). The public-JSON ingestion path no
longer works. Fix = authenticate via a registered Reddit app (OAuth / PRAW) for reads, not just
sends. See ROADMAP.md §1.

### Watcher (`backend/app/watcher.py`)
- Fetches via `www.reddit.com/search.json` (currently 403 — see above)
- Module-level `asyncio.Lock` prevents overlapping runs (startup task, scheduler, and the
  `/watcher/run` + `/watcher/backfill` endpoints can all trigger it)
- Per-term try/except so one bad term doesn't abort the whole run
- `fetch_posts` handles non-200, `RequestError`, and non-JSON (HTML error page) responses
- 2–3s sleep between terms; `time_filter` of `hour` (default) or `day` (backfill)
- Cross-post dedup (same author + title) and DB dedup (`post_exists`)
- Refreshes `reddit_upvotes` / `num_comments` on already-seen posts
- `get_search_terms()` returns `None` on DB error (→ fall back to config) vs `[]` when the
  user disabled all terms (→ skip the run). Empty no longer silently reverts to hardcoded.

### Filter pipeline (`is_obvious_skip`) — all pre-Claude, zero API cost
Title hiring-signal check, co-founder/`[for hire]`/job-seeker rejects, thin-body and
URL-only rejects, blocked subreddits + platforms, no-pay/scam phrases, location/onsite
restrictions, irrelevant stacks, microtask spam, NSFW.

### Scorer (`backend/app/scorer.py`) — ⚠️ MOCK
- `score_and_draft()` returns a hardcoded `{score: 7, …}` (line ~89). The real implementation
  (claude-agent-sdk) is commented out below it.
- System prompt, 1–10 rubric, 3-line message rules, anti-bot variation, and the 3-tier JSON
  parser (`_extract_and_validate`) are all written and ready.
- Needs the swap to the `anthropic` API SDK + a key — see ROADMAP.md §2.

---

## Phase 2 — Email Notifications ✅
Gmail SMTP-SSL (port 465), urgency in subject (HIGH 8+/MEDIUM 5-7/LOW 3-4), full post + draft
in body, pause/resume via `app_settings.notifications_enabled`. Now dispatched off the event
loop via `asyncio.to_thread` so SMTP doesn't block the watcher. Creds set in `.env`.

---

## Phase 3 — Dashboard UI ✅
Five pages, dark theme, Reddit-orange accent.
- **Feed** — dense table (score ring, author, subreddit badge, engagement, freshness), tabs
  (All/Drafts/Approved/Disapproved/Search), time filter (Past hour / Past 24h / All time),
  sort, sanitized local search, live Reddit search, pagination, realtime INSERT (dedups by id),
  per-post Draft/Delete, backfill button, dismissible SetupChecklist.
- **MessageReview** — sidebar w/ infinite scroll, full post panel, editable draft, countdown,
  auto-advance. Fetches all message statuses (cancelled/sent no longer show a misleading
  "no draft" empty state).
- **Queue** — approved messages by `send_after`, Send Now, react-query auto-refresh (30s).
- **Tracker** — sent history, react-query auto-refresh, manual outcome dropdown
  (ignored/responded/hired/ongoing → `messages.outcome`).
- **Settings** — Email Alerts toggle, Search Terms CRUD, editable Config rows (portfolio URL,
  DM cap, approval window) persisted to `app_settings`.
- Score legend/ring now matches the rubric: Strong 8+, Good 5–7, Weak 3–4.

---

## Phase 4 — Send Engine (dry-run only) ✅ built
- PRAW client, lazy init, requires all 4 Reddit env vars
- `DRY_RUN` (default true): logs, marks as `dry_sent` (kept separate from real `sent`)
- Daily DM cap enforced **before** the dry-run branch; counts `sent` + `dry_sent` by `sent_at`
- `send_dm()` writes `sent_at`; `process_auto_sends()` runs every minute; manual send via
  `POST /messages/{id}/send` (returns proper 404/422 on bad input)
- **Not wired:** pending→send auto-transition (BUG-3), never-DM-twice guardrail (BUG-5),
  real Reddit creds (need registered app). See BUGS.md / ROADMAP.md.

---

## Phase 5 — Reply Tracking ⬜ placeholder UI only
Schema exists (`reply_received`, `replied_at`, `outcome`); Tracker has the manual outcome
dropdown. Automated inbox polling not built — needs authenticated Reddit (same app as Phase 4).

---

## Phase 6 — Deployment ⬜ not started
Will **self-host** on an Ubuntu box with nginx (same approach as the portfolio and offroute
apps), not Oracle Cloud. See ROADMAP.md §7.

---

## Infrastructure & Config
- `backend/app/config.py`: interval 10min, approval window 2–5 (randomized), daily cap 20,
  retention 30d, `DRY_RUN` from env (default true), CORS origins from `CORS_ORIGINS`.
- Supabase project `dkjtgpcmgwdodsdgwnzg` — 4 tables (`posts`, `messages`, `app_settings`,
  `search_terms`). RLS on; backend uses service_role, frontend uses anon (anon currently has
  write access — see BUGS.md BUG-14).
- `.env` + `*.env` gitignored; `backend/.env.example` committed. No secrets tracked in git. ✅
- Frontend env: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`.

## Run locally
```bash
# backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm run dev   # http://localhost:5173
```
