# Reddit Outreach

Automated Reddit job-outreach tool. Watches Reddit for hiring posts, scores + drafts a
personalized DM with Claude, lets you review in a dashboard, and (eventually) auto-sends if you
don't intervene. Fullstack: FastAPI backend + React/Vite dashboard + self-hosted PostgreSQL.

> **Status at a glance (2026-10-18):** runs locally on self-hosted Postgres (migrated off
> Supabase). Auto-send and the never-DM-twice guard are done. Remaining to go live: Reddit's 403
> on unauthenticated reads (needs a registered app) and backend auth for production. Full detail
> in [`docs/AI_UPGRADE_PLAN.md`](docs/AI_UPGRADE_PLAN.md), [`docs/STATUS.md`](docs/STATUS.md),
> [`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/BUGS.md`](docs/BUGS.md),
> [`docs/SECURITY.md`](docs/SECURITY.md).

## Stack
- **Backend:** Python 3.11, FastAPI, APScheduler, httpx/PRAW, Claude (scorer) — `backend/app/`
- **Frontend:** React + Vite + react-query — `frontend/src/` (talks only to the backend API)
- **DB:** self-hosted PostgreSQL via SQLAlchemy 2.0 async + Alembic — tables `posts`, `messages`,
  `search_terms`, `app_settings`, `llm_calls`
- **Deploy (planned):** self-hosted Ubuntu + nginx (same as the portfolio/offroute apps)

## Run locally
```bash
# Postgres (one-time): create the DB; Alembic builds the schema + seeds terms/settings
createdb reddit_outreach

# Backend  → http://localhost:8000  (API docs at /docs)
cd backend
source venv/bin/activate          # recreate with python3.11 -m venv venv
pip install -r requirements.txt   # first time only
alembic upgrade head              # creates tables + seeds search terms/settings
uvicorn app.main:app --reload --port 8000

# Frontend → http://localhost:5173
cd frontend
npm install                       # first time only
npm run dev
```
Requires `backend/.env` (see `backend/.env.example`; set `DATABASE_URL`/`DATABASE_URL_SYNC`) and
`frontend/.env` (`VITE_API_URL`, defaults to `http://localhost:8000`).

## How it works
1. **Watcher** (every 10 min) searches Reddit for hiring terms, runs ~17 pre-filters, then
   scores + drafts with Claude. Posts scoring ≥3 are saved; a draft message is queued `pending`.
2. **Notifications** email you per saved post (pausable in Settings).
3. **Dashboard** — Feed → review/approve/edit drafts → Queue (approved) → Tracker (sent + outcome).
4. **Sender** (dry-run) would auto-send `pending` messages after a 2–5 min window, respecting a
   daily cap and (planned) a never-DM-twice guardrail.

## Current blockers / open work
| Item | State | Where |
|---|---|---|
| Reddit `search.json` 403 (unauth reads blocked) | **Blocking ingestion** | ROADMAP §0 / BUG-0 |
| Supabase → self-hosted Postgres | **Done** | AI_UPGRADE_PLAN 0.5 |
| Auto-send of pending messages | Done (toggle pending in final phase) | BUG-3 |
| Never-DM-twice guardrail | Done | BUG-5 |
| Real scorer (currently MOCK) | Deferred to final steps | ROADMAP §3 / AI_UPGRADE_PLAN |
| Backend auth (browser DB-write path removed) | Fix before deploy | SECURITY S1 |
| Reply tracking (Phase 5) | Placeholder | ROADMAP §5 |
| Deployment (self-host) | Not started | ROADMAP §6 |

User's plan: build everything out first; **auto-DM, real scoring, and deployment are the final
steps.** Reddit account `Upper-Vehicle2154`, karma ~19.

## Docs
- [`docs/AI_UPGRADE_PLAN.md`](docs/AI_UPGRADE_PLAN.md) — active phased plan (de-Supabase + AI upgrade)
- [`docs/STATUS.md`](docs/STATUS.md) — what's built, per phase
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — what's left, in order
- [`docs/BUGS.md`](docs/BUGS.md) — open + resolved bugs
- [`docs/SECURITY.md`](docs/SECURITY.md) — security review + pre-deploy checklist
- [`docs/project-brief.md`](docs/project-brief.md), [`docs/process-and-guardrails.md`](docs/process-and-guardrails.md) — original spec
