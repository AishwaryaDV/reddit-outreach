# Reddit Outreach — Process & Guardrails
**Source of truth | Last updated: May 2026 | Living document — update as we learn**

---

## Section 1: Search Terms

Search is done **globally across all of Reddit** — not limited to specific subreddits. The watcher cycles through all 14 terms every 2 minutes using Reddit's public search API (`reddit.com/search.json`).

### Active Search Terms
1. `hiring developer`
2. `hiring engineer`
3. `hiring full stack engineer`
4. `hiring react developer`
5. `hiring web developer`
6. `hiring web app developer`
7. `hiring remote developer`
8. `hiring freelance developer`
9. `looking for a website developer`
10. `looking for a web app developer`
11. `looking for a developer`
12. `need a developer`
13. `need a web developer`
14. `need a fullstack developer`

---

## Section 2: Time Filter

| Filter | Window | Default? | When to use |
|---|---|---|---|
| Past hour | 60 min | Yes — watcher default | Daily active use, catching posts first |
| Today | 24 hours | Yes — secondary | Morning catch-up |
| Past 3 days | 72 hours | No | Coming back after being away |
| Past week | 7 days | No | Occasional deep search only |

**UI note:** Dashboard has a dropdown to switch between these. Watcher always runs on `past hour`. Posts older than selected window are skipped and never stored.

---

## Section 3: Green Flags — Posts Worth DMing

Claude scores every post against these. A post needs to hit **most** of these to score 5+.

### Title signals
- `[Hiring]` tag at the start
- Title matches search terms
- Plain language works — "looking for a developer", "need someone to build my app"
- Specific role mentioned — React dev, fullstack, web app, frontend

### Post body signals
- Has a proper body — not just a title
- Describes the project or product clearly
- Mentions specific requirements — tech stack, features, timeline
- Mentions their role — founder, startup, small business owner, individual
- Has a budget range (even approximate)
- Mentions remote or async-friendly
- Asks for portfolio, experience, or to get in touch
- Feels like a real person writing about a real project
- Has questions or invites replies

---

## Section 4: Red Flags — Posts To Skip

Claude filters these out. Posts scoring 1–2 are **silently discarded and never stored.**

### Scam posts — highest priority
- Mentions budget upfront with zero project details
- Vague about actual work — only mentions stack and availability
- No body — just a title
- Asks for availability before describing the project
- Upwork, Fiverr, Freelancer links
- Too good to be true — "$5000/week for part time work"
- Contact via Telegram, WhatsApp, or external email immediately
- Poor grammar + vague promises
- Crypto, NFT, or blockchain payment only

### For Hire posts — always skip
- `[For Hire]` tag
- Someone describing their own skills looking for work
- "Available for hire", "open to opportunities", "looking for clients"

### Irrelevant types — always skip
- Sad story / asking for job help or advice
- Job board reposts — company HR posts
- Advice-seeking — "how do I find a developer?"
- Recommendations for tools or agencies
- Discussion, AMAs, opinion posts
- Co-founder only (no dev hire intent)

### Not a fit — skip
- Requires specific country or in-office attendance
- Tech stack completely outside experience
- Full-time employee only with visa sponsorship
- Budget explicitly under **$200 for a full project**

---

## Section 5: Claude Scoring Logic

Every post is scored before it reaches the dashboard.

| Score | Label | Action |
|---|---|---|
| 8–10 | Strong match | Show, high priority |
| 5–7 | Possible match | Show, normal priority |
| 3–4 | Weak match | Show, low priority |
| 1–2 | Skip | Discard silently — never stored in DB |

Claude also adds a **one-line reason** shown on each post card in the dashboard.

---

## Section 6: Message Template & Personalization Rules

### Base structure — 3 lines, no more

| Line | Purpose |
|---|---|
| Line 1 | Hook — references their post specifically |
| Line 2 | Value prop — relevant skill or experience |
| Line 3 | Portfolio — always last, always included |

### Real examples

**Variation A:**
> Hey saw your post, I've plenty of experience developing and deploying websites end to end
>
> Here's my portfolio — https://aishwaryadv.space

**Variation B:**
> Hey saw your post, I've plenty of experience developing and deploying websites end to end
>
> Checkout my portfolio — https://aishwaryadv.space

**Variation C (skill-specific):**
> React dev my whole career! 3YOE fullstack, MVP specialist
>
> My portfolio — https://aishwaryadv.space

### Personalization rules for Claude
- Extract what they specifically need — React, fullstack, MVP, landing page
- Match hook to their post — if they mention React, lead with React
- Match tone — casual post → casual message, formal → slightly more polished
- Portfolio link is **ALWAYS the last line, ALWAYS included** — non-negotiable
- Keep it short — **2–3 lines max, never more**
- Never sound like a cover letter
- Never mention rates or availability in the first message

---

## Section 7: Anti-Bot Variation Rules

| Message # | Variation level | What changes |
|---|---|---|
| 1–4 | Close variations | Same structure, slightly different wording |
| 5+ | Distinct | Different structure, different tone, different skill emphasis |

- Claude tracks the **last 4–5 messages sent** — no two can be too similar
- **Portfolio CTA rotates:** "Here's my portfolio", "Checkout my portfolio", "My work", "My portfolio", "See my work at"
- **Hook rotates:** "Saw your post", "This looks like a great fit", "Right up my alley", "Came across your post", "React dev here"

---

## Section 8: Sending Rules & Timing

| Rule | Detail |
|---|---|
| Approval window | 2–5 minutes, randomized per message |
| Within-batch delays | 45–90 seconds between messages in same batch |
| Batch size | 3–4 messages |
| Between sessions | Natural gap — hours apart based on when posts were found |
| Never DM twice | Same Reddit username never gets DMed twice |
| Portfolio always included | No exceptions |
| Max messages per day | Soft cap of **15–20 DMs/day** |

---

## Section 9: DB Retention Policy

| Post status | Retention |
|---|---|
| `new`, `drafted` | Auto-deleted after **30 days** (daily cleanup at 3am) |
| `approved`, `sent`, `cancelled` | Kept **indefinitely** (CRM history) |

---

## Section 10: Still To Be Added

- 10 real examples of posts the user **WOULD** DM
- 10 real examples of posts the user **WOULD NOT** DM
- Additional search terms discovered over time
- Edge cases as the system runs

**Process for improvement:** Every time the system gets a post wrong (false positive or false negative) — add it here. This is how the filter gets smarter.
