# Bugs

**Last audited: 2026-10-14 | Branch: version1**

Re-audited against live code. The July 11–16 sprint fixed most of the original list; those are
in the "Resolved" section at the bottom for history. Severity: **Critical** (blocks core
functionality / will crash on go-live), **High**, **Medium**, **Low**.

---

## OPEN

### BUG-0 (Critical, NEW): Reddit public JSON returns 403 — ingestion dead
**File:** `backend/app/watcher.py:26-41` (`fetch_posts`)
**Problem:** `www.reddit.com/search.json` now returns **403** for unauthenticated requests
(confirmed via direct curl, not app-specific). The watcher fetches 0 posts every run.
**Impact:** No new posts are ingested at all. Phase 1 is dead against live Reddit.
**Fix:** Authenticate — register a Reddit script app, move to PRAW/OAuth for reads. See ROADMAP §0.

### BUG-3 (Critical): Pending messages never auto-send
**File:** `backend/app/sender.py:98`
**Problem:** `process_auto_sends()` queries only `status=approved`. Watcher saves messages as
`pending`; nothing transitions them. Untouched messages sit forever; the UI countdown shows
"auto-sent" but nothing was sent.
**Impact:** The product's core promise ("sends automatically if no intervention") doesn't work.
**Fix:** `.in_("status", ["pending", "approved"])`. See ROADMAP §1 (needs a behavior decision).

### BUG-5 (Critical): No "never DM the same author twice" guardrail
**File:** not implemented
**Problem:** Nothing checks author history before drafting/sending. Same person in 3 subreddits
= 3 DMs.
**Impact:** Spam risk / account ban — the single most likely thing to get the account reported.
**Fix:** Before `send_dm`, skip if a prior `sent` message exists for that author. See ROADMAP §2.

### BUG-14 (High for prod, N/A locally): No auth + frontend writes via anon key
**File:** `backend/app/main.py` (all routes), `frontend/src/pages/*` (direct supabase writes)
**Problem:** Every API endpoint is open; the frontend DELETEs/UPDATEs/INSERTs directly with the
anon key (which ships in the public JS bundle), so Supabase RLS currently grants anon full write.
**Impact:** On a public host, anyone can trigger sends/watcher runs/config changes and
read/delete/modify all data. Fine on localhost only.
**Fix:** See docs/SECURITY.md and ROADMAP §4. Must be closed before deployment.

### BUG-7b (Low): State-changing endpoints exposed over GET
**File:** `backend/app/main.py:157-166` (`/watcher/run`, `/watcher/backfill`)
**Problem:** These mutate state but are GET — CSRF-able and cacheable/prefetchable.
**Fix:** Make them POST (and gate behind auth per BUG-14).

### BUG-18b (Low): Realtime INSERT ignores active filter/sort
**File:** `frontend/src/pages/Feed.jsx:117-124`
**Problem:** Dedup by id is now handled, but a new INSERT is still prepended even when it falls
outside the current time-filter or sort order.
**Fix:** Check the new post against the active filter before prepending.

### BUG-scorer-status (Low): `/status` misreports the scorer
**File:** `backend/app/main.py:71`
**Problem:** Hardcoded `"scorer": "claude-agent-sdk"` while the scorer is actually the mock.
**Fix:** Report mock vs real based on the actual code path / a flag.

### BUG-25 (Low, by design): Live search applies hiring filters
**File:** `backend/app/watcher.py` (`search_term` → `process_term`)
**Problem:** `/search/reddit` runs arbitrary queries through the hiring filters, so non-hiring
searches return 0. A UI note ("saves hiring posts only") was added to clarify.
**Fix (optional):** add a `skip_filters` param for manual searches.

---

## RESOLVED (July 11–16 sprint — verified in code 2026-10-14)

- **BUG-1** `search_terms` column mismatch — code aligned to `active`; empty vs error disambiguated (`d5ff4cc`).
- **BUG-2** `messages.updated_at` missing — now writes/queries `sent_at` (`1045b52`).
- **BUG-4** Dry-run polluted CRM — uses distinct `dry_sent` status; cap checked before dry-run (`1045b52`).
- **BUG-6** `manual_send` 500 vs 404 — now `maybe_single()` → proper 404/422.
- **BUG-7** No per-term error boundary — each `process_term` wrapped in try/except (`c5a77ef`).
- **BUG-8** Concurrent watcher runs — module-level `asyncio.Lock` + strong task refs (`c5a77ef`).
- **BUG-9** Watcher interval too aggressive — now 10 min (`eed4b71`).
- **BUG-10** Config/spec drift — interval 10, window 2–5 randomized, retention 30d (`eed4b71`).
- **BUG-11** Blocking SMTP in event loop — wrapped in `asyncio.to_thread` (`watcher.py:269`).
- **BUG-13** Feed search raw PostgREST injection — input sanitized `replace(/[,().%]/g,'')`.
- **BUG-15** Queue stale data — react-query auto-refresh (`5d979ee`).
- **BUG-16** Disabling all terms reverted to hardcoded — `get_search_terms` returns None vs [] (`d5ff4cc`).
- **BUG-19** "Today" filter mislabeled — renamed "Past 24h" (`050066f`).
- **BUG-20** Cancelled/sent showed misleading empty state — now fetches all statuses.
- **BUG-21** SetupChecklist dead checks — removed (`a15e158`).
- **BUG-22** Score legend vs rubric — aligned to Strong 8+/Good 5–7/Weak 3–4.
- **BUG-24** Engagement counts frozen — refreshed on re-seen posts (`91ebb99`).
- **BUG-26** React-query installed but unused — now used by Queue + Tracker.
