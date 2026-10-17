# Security Review

**Audited: 2026-10-14 | Branch: version1**

Scope: `backend/app/*` and `frontend/src/*`. Verdict: **safe for local dev, NOT safe to expose
publicly as-is.** Two high-severity issues must be fixed before self-hosting. No secrets are
leaked and no critical injection paths were found.

---

## High — must fix before deployment

### S1. No authentication on any API endpoint
`backend/app/main.py` — none of the routes require auth. Anyone who can reach the host can call
`POST /messages/{id}/send`, `GET /watcher/run`, `GET /watcher/backfill`, `POST /config`,
`POST /notifications/toggle`. On a public server this means strangers can trigger DM sends,
change your config, and spin the watcher.
**Fix:** `DASHBOARD_TOKEN` env var + a FastAPI dependency checking `Authorization: Bearer` on all
non-health routes; frontend stores the token and sends it on every request.

### S2. Frontend mutates the database directly with the anon key
`frontend/src/pages/Feed.jsx:132-133` (delete posts/messages),
`MessageReview.jsx:130-140` (approve/cancel), `Settings.jsx:103-128` (terms CRUD),
`Tracker.jsx:94` (outcome). The anon key is embedded in the public JS bundle. Because these
writes succeed, Supabase RLS currently grants `anon` INSERT/UPDATE/DELETE on your tables —
so anyone with the (public) anon key can wipe or alter all your data.
**Fix:** Restrict RLS so `anon` has **SELECT only**; route every mutation through the
authenticated backend (which uses the service-role key server-side).

---

## Medium

### S3. State-changing operations over GET (CSRF-able)
`/watcher/run` and `/watcher/backfill` are GET and mutate state — triggerable by a simple page
load, image tag, or prefetch. Combined with S1 (no auth).
**Fix:** Make them POST and gate behind auth.

### S4. No rate limiting
Combined with S1, trigger/send endpoints can be spammed (many watcher runs, repeated send
attempts against the daily cap).
**Fix:** Basic per-IP rate limiting on the trigger/send routes once auth is in.

---

## Low / informational

- **S5. CORS is not an auth boundary.** `allow_origins` is set from `CORS_ORIGINS`, but CORS only
  constrains browsers — non-browser clients ignore it. Don't rely on it for protection; S1 is the
  real gate.
- **S6. `/search/reddit?q=` is not an SSRF risk.** `q` is URL-encoded by httpx into a fixed
  `reddit.com` host; no arbitrary-URL fetch.
- **S7. Secrets handling is correct.** service-role key, Gmail app password, and (future) Reddit
  creds live only in `backend/.env`; `.env`/`*.env` are gitignored; nothing sensitive is tracked
  in git. ✅ Keep it that way — never commit `.env`.

---

## Checklist before going live
- [ ] S1 — bearer-token auth on all non-health endpoints
- [ ] S2 — Supabase RLS anon = SELECT only; mutations via backend
- [ ] S3 — watcher trigger endpoints → POST + auth
- [ ] S4 — rate limiting on trigger/send
- [ ] Confirm `DRY_RUN=false` is set **only** when you intend real sends
- [ ] Rotate the Supabase anon key if it was ever committed historically (it is public by design,
      but confirm RLS is the only thing protecting you)
