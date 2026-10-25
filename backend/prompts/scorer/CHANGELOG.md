# Scorer prompt changelog

Each version is a `vN.md` file. The active version is `PROMPT_VERSION` in `app/scorer.py`
and is recorded on every call in the `llm_calls` table, so eval results can be tied to the
exact prompt that produced them.

## v1 (2026-10-19)
Baseline rubric (1–10), 3-line message rules, anti-bot variation. Output is the structured
`ScoreResult` schema (`score, label, reasons, red_flags, budget_mentioned, draft`), enforced
natively on Gemini via `response_schema` and validated with Pydantic on both backends (retry
once on a validation failure). (Started the same day as free-text `{score, reason, draft}`;
moved to the structured schema.)

## v2 (2026-10-22)
Rebuilt the owner profile and loosened the skip rules after real gigs started flowing (v1
over-rejected them). Changes:
- **Profile:** now a fullstack + AI engineer (4 YOE) with AI engineering, backend, and frontend
  weighted EQUALLY — v1 framed the owner as a React-first fullstack dev, which down-ranked
  backend-only and AI gigs. Grounded in real stack/projects (React/Next/SvelteKit/TS,
  Python/FastAPI/Postgres, RAG/embeddings/LLM APIs; Offroute, SimuFlow, TripLedger).
- **AI/LLM work is in-scope and strong:** chatbots, RAG, agents, AI integrations, automation,
  prompt engineering. (Heavy ML research / model training stays out of scope.)
- **Crypto:** only "paid ONLY in crypto" / obvious crypto scams are skipped; building a real
  product for a web3 company that pays normally is scored on merit.
- **Small gigs:** only genuinely unpaid/trivial budgets are skipped; small/regional (e.g. INR)
  paid gigs now surface. Narrow web skills (HTML email, WordPress/Shopify) are in-scope.
Motivated by 3 real gigs v1 wrongly scored 1 (r/DevsForHire crypto full-stack, r/hiredev
backend contract, r/FreelanceIndia HTML email).

## v3 (2026-10-24)
Experience level is no longer a disqualifier: a role asking for FEWER years than the owner has
(junior / entry / 1-2 YOE) is still a fit — over-qualified is fine — so a lucrative under-level
gig gets surfaced instead of skipped. (Owner applies to these when the budget is good.)
