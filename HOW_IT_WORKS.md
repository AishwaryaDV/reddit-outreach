# How the Reddit Outreach Engine Works

This document explains the full pipeline — from how Reddit posts are discovered, filtered, and scored, to how they appear in the dashboard.

---

## Overview

The engine watches Reddit every 15 minutes for posts matching hiring-related search terms. It fetches posts, filters out obvious noise, scores genuine candidates using Claude AI, and surfaces them in a real-time dashboard for review.

No Reddit account or OAuth is required for reading. No Anthropic API key is required for scoring — it routes through the Claude Code CLI session.

---

## The Watcher Cycle

**Every 15 minutes**, the watcher runs automatically on startup via APScheduler.

### What happens in one cycle:

1. Loop through all 14 search terms
2. For each term: fire 1 request to Reddit's public JSON API fetching up to 50 posts from the last hour
3. Wait 2 seconds before the next term
4. For each post returned: run it through the filter pipeline

**Total per cycle:** 14 requests, ~40 seconds of active work, then idle until the next 15-minute tick.

### Reddit API details

- Endpoint: `https://www.reddit.com/search.json`
- Parameters: `q=<term>&sort=new&t=hour&limit=50`
- No authentication needed — Reddit's public JSON API is free to read
- `t=hour` means only posts from the last 60 minutes are returned
- Average load: ~1 request/minute (14 requests per 15-minute cycle)
- The 2-second gap between terms keeps us well within Reddit's rate limits

---

## The 14 Search Terms

```
hiring developer
hiring engineer
hiring full stack engineer
hiring react developer
hiring web developer
hiring web app developer
hiring remote developer
hiring freelance developer
looking for a website developer
looking for a web app developer
looking for a developer
need a developer
need a web developer
need a fullstack developer
```

---

## The Filter Pipeline

Each of the up to 50 posts per term passes through these checks before reaching Claude:

### 1. Has a Reddit post ID
Every valid Reddit post has a unique ID. If missing, skip. (Practically never triggered.)

### 2. Deduplication check
`post_exists(reddit_post_id)` queries the database. If the post is already saved, skip it.

This is the most powerful filter after the first run — since posts from the last hour overlap heavily between 15-minute cycles, most posts are already known. The same post can match multiple search terms but will only ever be scored once.

### 3. Obvious skip check (`is_obvious_skip`)
Hard rules that skip a post without calling Claude:
- Title contains `[for hire]` — the poster is offering services, not looking to hire
- Body is empty, `[deleted]`, or `[removed]` — no content to evaluate

Posts that pass all three checks are sent to Claude for scoring.

---

## Claude Scoring

**File:** `backend/app/scorer.py`  
**Function:** `score_and_draft(title, body, recent_drafts)`  
**Model:** Claude Haiku (fast, lightweight, sufficient for scoring)  
**SDK:** Claude Agent SDK — routes through your Claude Code CLI session, no separate API key needed

### What Claude does per post:
1. Reads the post title and body
2. Scores it 1–10 based on how likely it is to be a real paid web development opportunity
3. Writes a short reason for the score
4. If score ≥ 3, drafts a personalised outreach DM

### Scoring rubric (summary):
- **8–10:** Clear budget, specific scope, real project, actively looking
- **5–7:** Likely real but missing some details (no budget mentioned, vague scope)
- **3–4:** Borderline — might be worth a look but low confidence
- **1–2:** Irrelevant, scammy, or not a hiring post — skipped entirely, not saved

Posts scoring ≤ 2 are discarded. Posts scoring ≥ 3 are saved to the database.

### Anti-repetition
The 5 most recently sent DM drafts are passed to Claude as context so it varies the wording and avoids sending near-identical messages.

---

## Output: What Gets Saved

When a post passes scoring, the following is saved to Supabase:

**`posts` table:**
- Reddit post ID, title, body, author, subreddit
- `posted_at` — when the post was originally published on Reddit
- `detected_at` — when our watcher found it
- `score`, `score_reason`
- `status`: `drafted` (if a DM was written) or `new` (if score was too low for a draft)

**`messages` table** (if a draft was written):
- The draft DM
- `send_after` timestamp — a randomised delay before auto-send (currently 10 minutes)
- `status`: `pending` → `approved` or `cancelled`

---

## The Dashboard

**Frontend:** React + Vite + TailwindCSS  
**Real-time updates:** Supabase Realtime — new posts appear in the feed instantly via a Postgres INSERT subscription, no manual refresh needed.

### Feed page
- Shows all detected posts sorted by most recent
- Filter by: Past hour / Today
- Urgency border colour based on how old the original Reddit post is:
  - Green: posted < 30 minutes ago
  - Yellow: 30–90 minutes ago
  - Red: older than 90 minutes

### Message Review page
- Left: full post content, subreddit, score, reason, Reddit link
- Right: editable draft DM + countdown timer to auto-send
- Actions: Approve (sends now), Cancel (discards)

---

## Backfill

**What it is:** A manual one-shot trigger that runs the watcher with `t=day` instead of `t=hour`, fetching posts from the last 24 hours across all 14 terms.

**When to use it:** After restarting the server following a downtime gap longer than 1 hour. Under normal operation the regular 15-minute cycle with `t=hour` always overlaps — you never miss posts as long as the server is running.

**How to trigger it:** Click the **Backfill 24h** button in the top-right of the Feed page. New posts will flow in automatically via the realtime subscription.

**Why it exists:** Until the app is deployed to a 24/7 server, the backend runs locally and gets stopped/started. Backfill recovers any posts missed during those gaps.

> Note: Backfill fetches up to 700 posts (14 terms × 50 posts) and scores all new ones — use it deliberately, not casually, as it uses more Claude quota than a normal run.

---

## Database Cleanup

A daily cron job runs at 3:00 AM UTC and purges posts older than 15 days with status `new` or `drafted` (never actioned). Posts with status `sent` or `approved` are kept permanently as CRM history.

---

## Rate Limits Summary

| Resource | Limit | Our usage |
|---|---|---|
| Reddit requests | ~1 req/2s guideline | 14 req per 15 min (~1 req/min avg) |
| Claude scoring | Your Claude Pro quota | Only posts that pass all pre-filters |
| Supabase | Free tier | Read-heavy, very low write volume |
| Daily DM cap | 20 DMs/day (configurable) | Enforced at send time |
