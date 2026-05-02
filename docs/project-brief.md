# Reddit Outreach — Project Brief
**Personal Project | aishwaryadv.space | Started: May 2026 | Confidential**

---

## What We're Building

A fullstack web app that automates Reddit job outreach. It watches subreddits 24/7, detects relevant hiring posts, uses Claude AI to write a personalized version of a message template, notifies the user via email, and sends automatically if no intervention — so the user is always first to reach out.

**Problem solved:** Manual searching, clicking posts, DMing people — posts are missed when offline. This tool ensures no post is missed while keeping messages feeling human and personalized.

---

## Core Flow — End to End

Reddit post goes up → Watcher detects it within **1–2 minutes** → Claude reads the post and personalizes the message → User gets notified via **email** → User has **2–5 minutes (randomized)** to review, edit, or cancel in the dashboard → If no action, it sends automatically with human-like delays → Dashboard logs everything and tracks replies.

---

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Frontend | React + Vite | User's comfort zone as a frontend dev |
| Backend | Python + FastAPI | Best fit for Reddit API + async tasks |
| Database | Supabase (PostgreSQL) | Free tier, great UI, realtime support |
| Queue | Supabase table (not Redis) | Sufficient at volume, simpler setup |
| Reddit reading | Public JSON API (`reddit.com/search.json`) | No auth needed for Phase 1; PRAW added in Phase 4 for sending |
| Reddit sending | PRAW + Official Reddit API | Stable, no browser login needed |
| AI | Anthropic Claude API (Haiku) | ~$0.01–0.02/day at volume |
| Notifications | Email only (Gmail SMTP + App Password) | Telegram dropped — email is sufficient |
| Sending Mode | Mode 2 — auto with approval window | 2–5 min randomized window |
| Server | Oracle Cloud Free Tier | Free forever, 24/7 uptime (incident raised — pending) |
| Domain | aishwaryadv.space (Namecheap) | Subdomains: reddit.aishwaryadv.space, api.aishwaryadv.space |
| Process Manager | PM2 | Keeps all processes alive on server |
| Web Server | Nginx | Reverse proxy for domain routing |
| Supabase key (backend) | service_role key | Bypasses RLS; anon key reserved for frontend |

---

## Full Tech Stack

### Backend
- Python 3.11+
- FastAPI — REST API server
- PRAW — Official Reddit API wrapper (Phase 4+ only, for sending DMs)
- Reddit public JSON API — used for Phase 1–3 reading (no auth needed)
- Anthropic Python SDK — Claude Haiku message scoring + generation
- Supabase Python client — database reads/writes (service_role key)
- APScheduler — background job scheduling (watcher every 2 min, cleanup daily at 3am)

### Frontend
- React + Vite
- Supabase JS client — data fetching + realtime subscriptions (anon key)
- React Query — server state management
- TailwindCSS — styling

### Infrastructure
- Oracle Cloud Free Tier VM — ARM, 4 OCPU, 24GB RAM, Ubuntu 22.04 (pending setup)
- Nginx — reverse proxy, domain routing
- PM2 — process manager, auto-restart on crash
- Certbot — free SSL/HTTPS via Let's Encrypt
- Supabase — hosted PostgreSQL, free tier (portfolio project paused)

---

## Supabase Setup

- Project: `reddit-outreach` at `dkjtgpcmgwdodsdgwnzg.supabase.co`
- Portfolio project paused to stay within 2-project free tier limit
- Backend uses `service_role` key (bypasses RLS)
- Frontend uses `anon` key
- RLS is enabled on both tables; backend bypasses via service_role key
- Future migration: pg_dump → psql restore onto Oracle VM once server is ready

---

## Reddit Access

Phase 1–3: Reddit public JSON search API — no credentials needed.
```
https://www.reddit.com/search.json?q=hiring+developer&sort=new&t=hour&limit=25
```

Phase 4+: PRAW with script app credentials.
- Register app at `reddit.com/prefs/apps` → type: script
- Needs: `client_id`, `client_secret`, Reddit username + password
- **Blocker:** Reddit account (Upper-Vehicle2154) has ~10 karma — too low for app creation. Building karma naturally. Target: 50+ karma before Phase 4.

---

## Anthropic API Setup

- Separate from Claude Pro subscription — billed on usage at `console.anthropic.com`
- Model: Claude Haiku (`claude-haiku-4-5-20251001`)
- Cost: ~$0.001/post, ~$0.01–0.02/day at 20 posts/day
- Add $5 credit — lasts months
- **Status:** Account pending — API key not yet added to .env

---

## Message Sending Behavior

- **Approval window:** 2–5 minutes, randomized per message
- **Within a batch:** 45–90 second random gap between sends
- **Between sessions:** natural multi-hour gaps (when posts were discovered)
- Fully automatic once approved
- User notified the moment a post is detected
- If user edits or cancels within the window, that action takes priority
- Max **15–20 DMs/day** soft cap

---

## Dashboard UX — 5 Screens

### 1. Feed (main view)
- Live list of all detected posts
- Each card: subreddit, title, what they need, time posted, Claude score badge, urgency color
- **Green** = under 30 mins, **Yellow** = 30–90 mins, **Red** = over 90 mins
- Realtime updates via Supabase subscription

### 2. Message Review
- Left panel: full original post content
- Right panel: AI-drafted message, fully editable inline
- Countdown timer until auto-send
- Buttons: Approve & Queue / Edit then Approve / Cancel

### 3. Queue
- All approved messages waiting to send
- Shows estimated send time
- Can pause, reorder, or cancel any message

### 4. Tracker / CRM
- Every DM sent: timestamp, post, subreddit
- Reply status: waiting / replied (with timestamp) / ignored
- Outcome: ignored / responded / hired / ongoing — manual
- Subreddit performance stats

### 5. Settings
- Subreddit watchlist, keyword list, message template, approval window range, notification preferences

---

## Project Phases & Timeline

| Phase | What | Status | Estimated Days |
|---|---|---|---|
| 1 | Reddit Watcher + AI Draft | ✅ Done (API key pending) | 2–3 days |
| 2 | Notifications (Gmail) | ✅ Done (Gmail creds pending) | 1 day |
| 3 | Dashboard UI | 🔨 In progress | 4–5 days |
| 4 | Send Engine (PRAW) | ⏳ Blocked on Reddit karma | 2 days |
| 5 | Reply Tracking | ⏳ Pending | 1–2 days |
| 6 | Deployment + Domain | ⏳ Blocked on Oracle server | 1–2 days |

---

## Database Schema

### Table: `posts`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| reddit_post_id | text | Reddit's post ID, used for deduplication |
| subreddit | text | Which subreddit |
| title | text | Post title |
| body | text | Full post content |
| author | text | Reddit username of poster |
| posted_at | timestamptz | When they posted on Reddit |
| detected_at | timestamptz | When our watcher found it (default: now()) |
| score | integer | Claude score 3–10 (null if no API key) |
| score_reason | text | One-line Claude reasoning |
| status | text | new / drafted / approved / sent / cancelled |

**Cleanup rule:** Posts with status `new` or `drafted` are auto-deleted after 30 days. Posts with status `sent`, `approved`, or `cancelled` are kept indefinitely (CRM history).

### Table: `messages`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| post_id | uuid | FK → posts (cascade delete) |
| draft | text | Claude's personalized message draft |
| final_message | text | What was actually sent |
| send_after | timestamptz | Auto-send time (now + random 2–5 min) |
| sent_at | timestamptz | Actual send timestamp |
| created_at | timestamptz | Row created at (default: now()) |
| status | text | pending / approved / sent / cancelled |
| reply_received | boolean | Did they reply? |
| replied_at | timestamptz | When they replied |
| outcome | text | ignored / responded / hired / ongoing |

---

## Oracle Server Setup (pending)

- **Status:** Signup failed twice (ISP/card BIN rejection). Incident ticket raised with Oracle support.
- Home region: India South (Hyderabad) — `ap-hyderabad-1`
- Shape: VM.Standard.A1.Flex — 4 OCPU, 24GB RAM (always-free Ampere tier)
- OS: Ubuntu 22.04
- **Impact:** Zero on Phases 1–5. Server only needed for Phase 6 (deployment).

### Ports to open
- 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (FastAPI dev), 3000 (Vite dev)

### Domain routing (Phase 6)
| URL | Points To |
|---|---|
| aishwaryadv.space | Vercel (existing personal site — unchanged) |
| reddit.aishwaryadv.space | Oracle VM → React + Vite frontend |
| api.aishwaryadv.space | Oracle VM → FastAPI backend |

---

## Environment Variables

```env
SUPABASE_URL=https://dkjtgpcmgwdodsdgwnzg.supabase.co
SUPABASE_KEY=<service_role key>
ANTHROPIC_API_KEY=<pending>
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
NOTIFY_EMAILS=your@gmail.com  # comma-separated for multiple
```
