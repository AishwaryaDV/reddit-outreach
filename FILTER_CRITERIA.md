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

## Filter 4 — Job seeker patterns (not a hirer)

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

---

## Filter 5 — No-pay and scam signals

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

The `_JOB_SEEKER_PHRASES` and `_NO_PAY_PHRASES` lists in `watcher.py` map directly to Filters 4 and 5 above.
