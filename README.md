# Reddit Outreach

Automated Reddit job-outreach tool. Watches Reddit for hiring posts, scores + drafts a
personalized DM with Claude, lets you review in a dashboard, and (eventually) auto-sends if you
don't intervene. Fullstack: FastAPI backend + React/Vite dashboard + Supabase.

> **Status at a glance (2026-10-14):** builds and runs locally; Supabase live. Three things gate
> going live — Reddit now 403s unauthenticated reads, auto-send isn't wired, and there's no auth
> for production. Full detail in [`docs/STATUS.md`](docs/STATUS.md),
> [`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/BUGS.md`](docs/BUGS.md),
> [`docs/SECURITY.md`](docs/SECURITY.md).

## Stack
- **Backend:** Python 3.11, FastAPI, APScheduler, httpx/PRAW, Claude (scorer) — `backend/app/`
- **Frontend:** React + Vite + react-query — `frontend/src/`
- **DB:** Supabase (Postgres) — tables `posts`, `messages`, `search_terms`, `app_settings`
- **Deploy (planned):** self-hosted Ubuntu + nginx (same as the portfolio/offroute apps)

## Run locally
```bash
# Backend  → http://localhost:8000  (API docs at /docs)
cd backend
source venv/bin/activate          # venv is committed-adjacent; recreate with python3.11 -m venv venv
pip install -r requirements.txt   # first time only
uvicorn app.main:app --reload --port 8000

# Frontend → http://localhost:5173
cd frontend
npm install                       # first time only
npm run dev
```
Requires `backend/.env` (see `backend/.env.example`) and `frontend/.env`
(`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`).

**If everything suddenly errors / DNS is NXDOMAIN:** the Supabase free-tier project auto-pauses
after ~7 days idle. Resume it at https://supabase.com/dashboard (project `dkjtgpcmgwdodsdgwnzg`).

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
| Auto-send of pending messages not wired | Open (core promise) | ROADMAP §1 / BUG-3 |
| Never-DM-twice guardrail | Open (safety) | ROADMAP §2 / BUG-5 |
| Real scorer (currently MOCK) | Deferred to final steps | ROADMAP §3 |
| No API auth; frontend writes via anon key | Fix before deploy | SECURITY S1/S2 |
| Reply tracking (Phase 5) | Placeholder | ROADMAP §5 |
| Deployment (Phase 6, self-host) | Not started | ROADMAP §6 |

User's plan: build everything out first; **auto-DM, real scoring, and deployment are the final
steps.** Reddit account `Upper-Vehicle2154`, karma ~20.

## Docs
- [`docs/STATUS.md`](docs/STATUS.md) — what's built, per phase
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — what's left, in order
- [`docs/BUGS.md`](docs/BUGS.md) — open + resolved bugs
- [`docs/SECURITY.md`](docs/SECURITY.md) — security review + pre-deploy checklist
- [`docs/project-brief.md`](docs/project-brief.md), [`docs/process-and-guardrails.md`](docs/process-and-guardrails.md) — original spec
