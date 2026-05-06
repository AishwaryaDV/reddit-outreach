# Filter Criteria

This document is the source of truth for all pre-Claude filters applied in `backend/app/watcher.py → is_obvious_skip()`.

**Whenever you add, remove, or change a filter rule — update both this doc and the code so they stay in sync.**

---

## Filter 1 — Offering services (not hiring)

Applied to: **title**

Skip if title contains:
- `[for hire]`
- Starts with `[h]` (Reddit shorthand for "have" = poster is selling their skills)

---

## Filter 2 — No content

Applied to: **body**

Skip if body is:
- Empty
- `[deleted]`
- `[removed]`

---

## Filter 3 — Minimum body length

Applied to: **body**

Skip if body is under **150 characters**.

Real hiring posts describe scope, timeline, and requirements. Very short posts ("hey need a dev hmu") are not worth scoring.

---

## Filter 4 — Short title + thin body (combined)

Applied to: **title + body combined**

Skip if title is under **20 characters** AND body is under **300 characters**.

A short title alone is not enough to skip — sometimes that's all the context there is. But a short title paired with a thin body is a strong signal of a low-effort post not worth scoring.

---

## Filter 5 — URL-only body

Applied to: **body**

Strip all URLs from the body. If the remaining text is under **50 characters**, skip.

Posts that are essentially just a link with no description have no context for Claude to evaluate.

---

## Filter 6 — Job board subreddit with scraped listing

Applied to: **subreddit + body**

If the subreddit name contains `"job"` AND the body (after stripping URLs) is under **200 characters**, skip.

These are automated scraper bots that cross-post job board listings to Reddit with a link and a one-liner. Not genuine Reddit posts.

---

## Filter 7 — Job seeker patterns (not a hirer)

Applied to: **title**

Skip if title contains any of:
- `looking for work`
- `looking for a job`
- `open to work`
- `available for work`
- `seeking work`
- `seeking opportunities`
- `portfolio review`
- `rate my portfolio`
- `just launched`
- `just finished`
- `hire me`
- `looking for advice`
- `looking for suggestion`
- `looking for suggestions`

---

## Filter 8 — Blocked platforms

Applied to: **title + body + author**

Skip if any of the following appear in the title, body, or match the post author exactly:
- `micro1` (recruitment platform that posts generic listings on Reddit)

To add more: append to `_PLATFORM_BLOCKLIST` in `watcher.py` and list here.

---

## Filter 9 — No-pay and scam signals

Applied to: **title + body combined**

Skip if either contains any of:
- `revenue share`
- `rev share`
- `sweat equity`
- `equity only`
- `unpaid`
- `no budget`
- `no pay`
- `work for free`
- `pro bono`
- `volunteer`
- `student project`
- `school project`
- `class project`
- `uni project`
- `spec work`

---

## Filters under consideration (not yet implemented)

- **No pay/budget signal** — skip if neither title nor body contains any of: `budget`, `paid`, `pay`, `rate`, `hourly`, `salary`, `compensation`, `$`, `€`, `£`. Useful but aggressive — may produce false negatives on genuine posts that don't mention budget upfront. Hold until sample posts are reviewed.

---

## How to update filters

1. Edit the relevant section in this doc
2. Mirror the exact change in `backend/app/watcher.py` inside `is_obvious_skip()`
3. Commit both files together

**Code mapping:**
- Filters 1–6: inline logic in `is_obvious_skip()`
- Filter 7 → `_JOB_SEEKER_PHRASES` list
- Filter 8 → `_PLATFORM_BLOCKLIST` list
- Filter 9 → `_NO_PAY_PHRASES` list
