# Roadmap — What Needs To Be Done

**Last updated: 2026-10-14 | Branch: version1**

Ordered by dependency. The July schema/config/URL/CORS fixes from the old roadmap are **done**
(see STATUS.md) and have been removed from this list. User's stated plan: build everything out
first; **auto-DM, real scoring, and deployment are the final steps.**

---

## 0. NEW BLOCKER — Reddit public JSON now 403s (do this first)

Reddit started returning **403** for unauthenticated `www.reddit.com/search.json` requests
during the idle months (confirmed via direct curl). The watcher can't ingest new posts at all
until we authenticate. This also resolves itself into the Reddit-app work we needed anyway.

**Fix:** Register a Reddit **script app** at reddit.com/prefs/apps (no karma requirement for
registration). Move `fetch_posts()` from raw httpx on `search.json` to authenticated access —
either PRAW (`reddit.subreddit("all").search(...)`) or OAuth'd httpx against `oauth.reddit.com`.
Add `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` to `.env`.
Account: `Upper-Vehicle2154`, karma now ~20.

> Reads work regardless of karma. **Sending** DMs is the risky part — 20 karma is still low for
> DMing strangers, so keep `DRY_RUN=true` and hold real sends for the final step (and warm the
> account up more first).

---

## 1. Auto-Send Logic (the product's core promise) — BUG-3

`process_auto_sends()` only queries `status=approved`. Messages are saved as `pending` and
nothing transitions them, so nothing ever auto-sends. The UI countdown hits 0:00 and lies.

**Fix:**
1. `sender.py` query → `.in_("status", ["pending", "approved"]).lte("send_after", now)`
   (pending past its window = no intervention = send; Disapprove already sets `cancelled`).
2. Add batch guardrails: max 3–4 per run, `await asyncio.sleep(randint(45,90))` between sends.

**Decision needed from user:** confirm "pending past window → auto-send" is the intended
behavior (vs. requiring an explicit approve). This changes the whole product behavior.

---

## 2. Never-DM-the-same-author-twice guardrail — BUG-5

No code checks author history before sending. Same person posting in 3 subreddits = 3 DMs.
Single most likely thing to get the account reported.

**Fix:** Before `send_dm`, query for any prior `sent` message joined to a post with the same
`author`; skip + mark `cancelled` if found. Optionally also check at scoring time.

---

## 3. Real Scorer (replace MOCK) — final step

`scorer.py:~89` returns a hardcoded score 7. Real impl (claude-agent-sdk) is commented out.
The Agent SDK spawns a CLI subprocess per call — too heavy at 14 terms × 50 posts / 10 min,
and it burned the Claude Pro quota.

**Fix:** Switch to the `anthropic` Python SDK (`pip install anthropic`,
`client = anthropic.AsyncAnthropic()`, `model="claude-haiku-4-5-20251001"`, `max_tokens≈300`).
Keep `_extract_and_validate()`. Add `ANTHROPIC_API_KEY` to `.env` and a `SCORER_MOCK=true`
flag for pipeline testing. Remove `claude-agent-sdk` from requirements, add `anthropic`.
~$0.001/post at Haiku prices.

**Decision needed from user:** confirm the SDK swap + get an API key at console.anthropic.com.

---

## 4. Security hardening (before deploy) — BUG-14

Currently zero auth and the frontend mutates the DB directly with the anon key. Fine on
localhost; must be closed before self-hosting. See docs/SECURITY.md for the full list.

- Add a `DASHBOARD_TOKEN` env var + FastAPI dependency checking `Authorization: Bearer <token>`
  on all non-health endpoints.
- Make state-changing endpoints POST (not GET): `/watcher/run`, `/watcher/backfill`.
- Lock Supabase RLS: anon = SELECT only. Route all mutations (delete/approve/cancel/terms)
  through the authenticated backend instead of the frontend anon client.
- Optional: basic rate limiting on trigger/send endpoints.

---

## 5. Phase 5 — Reply Tracking

Blocked on the same Reddit app as §0/sending. Schema already exists.
1. Scheduler job every 5 min → `check_replies()` in a new `reply_checker.py`.
2. PRAW inbox read; match sender to a `sent` message's author; set `reply_received`/`replied_at`.
3. Tracker already has the manual outcome dropdown; replace the static "no reply yet".
4. Add subreddit performance stats (group-by on posts⋈messages).

---

## 6. Phase 6 — Deployment (self-host)

**Plan: self-host on Ubuntu + nginx**, same as the portfolio and offroute apps (Oracle dropped).

- Frontend: `npm run build` → serve `dist/` via nginx.
- Backend: uvicorn/gunicorn under systemd or PM2; nginx reverse-proxy to it.
- Domains: `reddit.aishwaryadv.space` → frontend, `api.aishwaryadv.space` → backend.
- Certbot for SSL; set `CORS_ORIGINS`, `VITE_API_URL`, `DASHBOARD_TOKEN`, and `DRY_RUN` per env.
- Keep the watcher process alive (systemd) and confirm Supabase won't idle-pause (a live
  deployment hitting it regularly should prevent the 7-day auto-pause).

---

## 7. Nice-to-haves (not blocking)

- Realtime INSERT handler respects the active time-filter/sort before prepending (currently
  dedups by id but can show a post outside the current filter).
- `/status` reports a hardcoded `"scorer": "claude-agent-sdk"` — make it reflect mock vs real.
- Settings: message-template editor, subreddit watchlist (both can use `app_settings`).
- Live search UX: it intentionally applies hiring filters; UI note added — consider a
  `skip_filters` option for arbitrary queries (BUG-25).

---

## Suggested execution order

```
0. Reddit auth (fixes 403 ingestion)        — unblocks the whole pipeline
1. Auto-send logic (BUG-3)                  — needs user decision on semantics
2. Never-DM-twice guardrail (BUG-5)         — safety before any real send
3. Security hardening (BUG-14)              — before deploy
--- final steps (user's call) ---
4. Real scorer swap (needs API key)
5. Real sends: set DRY_RUN=false (needs karma warm-up)
6. Reply tracking (Phase 5)
7. Deployment (Phase 6, self-host)
```
