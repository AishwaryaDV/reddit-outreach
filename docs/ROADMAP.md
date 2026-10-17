# Roadmap — What Needs To Be Done

**Last updated: 2026-10-16 | Branch: fix/open-bugs-sweep**

Ordered by dependency. The July schema/config/URL/CORS fixes from the old roadmap are **done**
(see STATUS.md). BUG-3 (auto-send) and BUG-5 (DM-twice guard) were fixed on branch
`fix/open-bugs-sweep` (2026-10-16). User's stated plan: build everything out first;
**auto-DM, real scoring, and deployment are the final steps.**

> **AI Upgrade Spec (docs/reddit-outreach-ai-upgrade-spec.pdf, 2026-10-11).** The bigger
> direction for this repo: turn it into a portfolio-grade AI pipeline — golden-dataset scorer
> evals (precision/recall/F1, Spearman), structured Pydantic outputs, prompt versioning, an
> `llm_calls` cost/latency table + `/metrics` page, an LLM-as-judge for drafts, guardrails
> (allowlist/profile.yaml/prompt-injection), and replay-mode portability. Its order of work
> starts with **Workstream 5a** (`llm_client.py` wrapper + replay mode + `llm_calls` logging).
> **Model decision (confirmed by user 2026-10-16):** Claude Agent SDK = primary scorer,
> Gemini (Flash, free tier) = fallback + CI + draft judge. This supersedes the old §3 below.
> Spec also wants **auto-send opt-in and OFF by default** (see §1).

---

## 0. NEW BLOCKER — Reddit public JSON now 403s (do this first)

Reddit started returning **403** for unauthenticated `www.reddit.com/search.json` requests
during the idle months (confirmed via direct curl). The watcher can't ingest new posts at all
until we authenticate. This also resolves itself into the Reddit-app work we needed anyway.

**Fix:** Register a Reddit **script app** at reddit.com/prefs/apps (no karma requirement for
registration). Move `fetch_posts()` from raw httpx on `search.json` to authenticated access —
either PRAW (`reddit.subreddit("all").search(...)`) or OAuth'd httpx against `oauth.reddit.com`.
Add `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` to `.env`.
Account: `Upper-Vehicle2154`, karma ~19 (3y-old verified account; registration needs no karma).

> Reads work regardless of karma. **Sending** DMs is the risky part — ~19 karma is still low for
> DMing strangers (3y account age helps), so keep `DRY_RUN=true` and hold real sends for the final
> step (and warm the account up more first).

---

## 1. Auto-Send Logic (the product's core promise) — BUG-3 ✅ DONE (needs a toggle)

**Fixed (ae5145c):** `process_auto_sends()` now includes `pending` past its `send_after`
window, ordered by `send_after`, capped at `AUTO_SEND_BATCH=4` per run. The mechanism works.

**⚠️ Open decision — reconcile with the AI Upgrade Spec.** The spec (Workstream 4b) wants
**human approval required by default; auto-send opt-in and OFF by default** (automated DMs can
violate Reddit spam rules, and a reviewer of the repo will check this). My fix currently makes
pending auto-send *unconditionally*. Recommended reconciliation: gate the pending branch behind
an `auto_send_enabled` setting in `app_settings` (default `false`); the code path stays, the
toggle controls it. Nothing actually sends today anyway (`DRY_RUN=true`), so no urgency — but
decide before real sends. Remaining nice-to-have: `asyncio.sleep(randint(45,90))` between sends.

---

## 2. Never-DM-the-same-author-twice guardrail — BUG-5 ✅ DONE

**Fixed (dbfcec3):** `send_dm` now calls `_already_messaged(author, exclude_post_id)` — skips
and marks the message `cancelled` if that author already has a `sent`/`dry_sent` post.
Case-insensitive; covers both auto-send and manual send.

---

## 3. Real Scorer + LLM layer (per AI Upgrade Spec) — final steps

`scorer.py:~90` returns a hardcoded score 7 (`SCORER_MODE="mock"`). The real claude-agent-sdk
impl is commented out below it.

**Model decision (user-confirmed 2026-10-16):** keep **Claude Agent SDK (Haiku) as primary**,
add **Gemini (Flash, free tier) as fallback** — *not* a swap to the `anthropic` API SDK (my
earlier recommendation here was wrong; the spec keeps the Agent SDK / Claude Code login path so
there's no API bill, just an API-equivalent `total_cost_usd` estimate). The old quota problem is
solved by the spec's approach, not by switching SDKs: response caching, 50-post dev subsets, and
a per-day quota guard that pauses scoring when hit.

**Per the spec (do in this order):**
1. **Workstream 5a** — `backend/app/llm_client.py` wraps every model call (score/draft/judge)
   behind two backends: `claude_sdk` and `gemini`. Pipeline never imports either SDK directly.
   Fallback: try Claude, on timeout/error/quota retry once then fall back to Gemini; log
   `backend` + `fell_back`. Add `LLM_MODE=replay` (serves `evals/cache/`) vs `live`.
2. **Workstream 3** — `llm_calls` Supabase table (tokens, cost, latency, parse_ok) + `/metrics`
   page + quota guard. Everything after needs real cost numbers.
3. **Structured outputs (2a)** — `ScoreResult` Pydantic schema via the SDK's `output_format` /
   Gemini JSON-schema; split scoring and drafting into two calls. Replaces `_extract_and_validate`.
4. **Prompts as files (2b)** — `prompts/scorer/v1.md`, `v2.md` + CHANGELOG; record
   `prompt_version` + `model` on each saved post.
5. Flip `SCORER_MODE` to the real backend once the wrapper is in.

**Owner to-dos (from the spec, blocking parts of this):** create a free `GEMINI_API_KEY` in
Google AI Studio + note the current free rate limits; add it to `backend/.env` and a GitHub
Actions secret; ensure Claude Code is logged in on the backend host; label ~250 posts for the
golden dataset. See the full spec PDF in `docs/`.

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
