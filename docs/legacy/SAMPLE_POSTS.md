# Sample Posts Reference

Use this doc to log real Reddit posts as examples of what to skip and what to DM.
When enough good examples are collected, these will inform tighter filter rules and Claude's scoring prompt.

**Format:** Paste the post title + body, then add a note on why it's good or bad.

---

## BAD POSTS — Posts to skip

---

### BAD-01 — Location restricted (US only)

**Why skip:** Requires US location. Remote-first but geography-locked. Not relevant for international freelancers.
**Filter catch:** ❌ Not currently caught — candidate for a future location filter.

```
Looking for a developer experienced in Python, JavaScript, or TypeScript. You should be
comfortable building and maintaining applications with clean, scalable code. C# is a plus.
This is not a temporary contract. Starting part-time, but you must be available to transition
to full-time within 1–2 months.
Must be located in America
Must have B2 or C1 English level
```

---

### BAD-02 — Micro1 recruitment post

**Why skip:** Micro1 is a third-party recruitment platform. Posts are generic, link to their job portal, and are not direct client posts. Apply-via-link process, not a DM opportunity.
**Filter catch:** ✅ Caught by platform blocklist (`micro1` in body + author)

```
Interview process: There is typically an application review and a technical/AI-based assessment.
Be ready to explain your O3DE experience, your Python/C++ work, and any simulation or game
engine projects you've built.
Apply here: https://jobs.micro1.ai/post/10b6ac1c-a009-44ca-bc88-5c4c29d92421?referralCode=...
If this sounds like you, apply. If not, no worries. I'll be posting more remote opportunities
across different skill sets.
```

---

### BAD-03 — Job board scrape / cross-post

**Why skip:** Auto-posted from a third-party job board (devitjobs.com). Not a direct Reddit hire — the person is not reachable by DM, just linking to an external listing. Also micro1.
**Filter catch:** ✅ Caught by platform blocklist (micro1) + likely URL-only body filter

```
[HIRING][San Francisco Bay Area, California, Python, Remote]
🏢 micro1, based in San Francisco Bay Area, California is looking for a Fullstack Developer (Python/React)
⚙️ Tech used: Python, AI, AWS, FastAPI, Support, LLM, React, SQL, TypeScript
💰 $140,000 - 200,000 / year
📝 More details and option to apply: https://devitjobs.com/jobs/micro1-Fullstack-Developer-PythonReact/rdg
```

---

### BAD-04 — Staffing agency / English skills focus

**Why skip:** Not a direct client. Sounds like a staffing agency recruiting developers to place with their clients ("manage the clients based on your strengths"). The focus on English communication over technical skills is a red flag. Low hourly rate for a dev role.
**Filter catch:** ❌ Not currently caught — needs a future filter or Claude scoring to catch it.

```
If you have at least 1 year of software development experience and good English communication
skills, we'd love to work with you. This is a great opportunity to grow in a flexible,
developer-friendly environment — without unnecessary meetings.
What you'll do:
* manage the clients based on your strengths and technical skills
Details:
* 💰 Hourly Rate: $20 – $30 (based on experience)
* 🌍 Remote work with flexible schedule
* ⏱️ Part-time options
Interested? Send me dm
```

---

### BAD-05 — Proxy interviewer / not a dev role

**Why skip:** Not a developer role at all. Looking for someone to conduct interviews on behalf of clients — grey area / likely a scam. Completely irrelevant.
**Filter catch:** ❌ Not currently caught — candidate for a role-type filter or Claude to score low.

```
[Hiring] [Remote] [USA / EU] - Interviewer

We're looking for a male (21+) with strong English skills to join our team as a Proxy Interviewer.
💼 Role
• Conduct interviews on behalf of clients
• Communicate clearly and confidently in English
• Maintain professionalism and confidentiality
🧠 Requirements
• European national, male, 21+
• Excellent spoken & written English
• Strong communication skills
• Reliable and punctual
💰 Compensation
• Starting from $300/month (growth based on performance up 500$)
📩 Apply by DM with your details and experience.
```

---

### BAD-06 — Onsite / in-person role

**Why skip:** Requires physical presence. Only remote opportunities are relevant.
**Filter catch:** ✅ Filter 11 — `_ONSITE_PHRASES`

*(More examples to be added)*

---

### BAD-07 — Micro1 job board scrape (FinTech variant)

**Why skip:** Same pattern as BAD-03. Auto-cross-posted from devitjobs.com by micro1. Not a direct hire.
**Filter catch:** ✅ Caught by platform blocklist (micro1) + URL-only body filter

```
[HIRING][San Francisco Bay Area, California, JavaScript, Remote]
🏢 micro1, based in San Francisco Bay Area, California is looking for a Fullstack Engineer (FinTech Experience)
⚙️ Tech used: JavaScript, AWS, Lambda, CI/CD, CloudWatch, Cypress, Docker, EC2, Git
💰 $140,000 - 200,000 / year
📝 More details and option to apply: https://devitjobs.com/jobs/micro1-Fullstack-Engineer-FinTech-Experience/rdg
```

---

### BAD-08 — Microtask / data entry spam

**Why skip:** Not a development role. Microtask (typing job) posted as if it were a dev opportunity. Signals: "typing speed", "upvote the post", "slots available", "hurry up".
**Filter catch:** ✅ Caught by microtask phrase filter

```
Hello everyone. Guys who have good typing speed and can work upto 4 hours everyday please
upvote the post and DM me. You will be paid INR 300 - 500 depending upon different factors.
There are 42 slots available right now. Hurry up!!!
```

---

### BAD-09 — Irrelevant tech stack (COBOL) + location restricted

**Why skip:** COBOL is a legacy mainframe language with zero relevance to web/fullstack development. Also US only.
**Filter catch:** ✅ Caught by irrelevant stacks filter (title: "COBOL") + location filter ("US only")

```
[Hiring] [Remote] [US] - COBOL Code Reading / Writing Expert $80-$100/hour (US only)

We are looking for experienced COBOL developers who can read, understand, debug, and write
production-quality COBOL code. You will work on tasks that help train and evaluate AI models
on legacy software engineering workflows, especially mainframe-style codebases.
[...]
* Please apply with the link - https://t.mercor.com/tt8EW
```

---

### BAD-10 — Mercor recruitment platform

**Why skip:** Mercor is a third-party recruitment platform (same pattern as Micro1). Posts link to their platform with an apply-via-link process, not a DM. Not a direct client.
**Filter catch:** ✅ Caught by platform blocklist (`mercor` in body/author)

*See BAD-09 body — Mercor link: `https://t.mercor.com/...`*

---

## Filter gaps identified from bad posts

| Bad post type | Currently caught? | Filter |
|---|---|---|
| US/location-only requirement | ✅ Yes | Filter 10 — `_LOCATION_PHRASES` |
| Onsite / in-person roles | ✅ Yes | Filter 11 — `_ONSITE_PHRASES` |
| Micro1 posts | ✅ Yes | Filter 8 — `_PLATFORM_BLOCKLIST` |
| Mercor posts | ✅ Yes | Filter 8 — `_PLATFORM_BLOCKLIST` |
| Job board scrapes | ✅ Yes | Filter 6 + Filter 8 |
| Microtask / spam | ✅ Yes | Filter 12 — `_MICROTASK_PHRASES` |
| Irrelevant tech stack (COBOL, Electron) | ✅ Yes | Filter 13 — `_IRRELEVANT_STACKS` |
| NSFW posts | ✅ Yes | Filter 14 — `over_18` field check |
| Blocked subreddits | ✅ Yes | Filter 15 — `_SUBREDDIT_BLOCKLIST` |
| Staffing agency / English focus | ❌ No | Claude scoring (low score) |
| Proxy interviewer / non-dev role | ❌ No | Claude scoring (low score) |

---

## Notes

- Paste new examples under the relevant section
- Mark filter catch status: ✅ caught / ❌ not caught / ⚠️ partially caught
- When a pattern repeats across multiple bad posts, flag it — that's a candidate for a new filter rule in `FILTER_CRITERIA.md`
