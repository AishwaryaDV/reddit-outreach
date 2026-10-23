# Context engineering — the scorer prompt

What actually goes into the model for each scoring call, what we compress, and why.

## What goes into the prompt

Each `complete("score", …)` call is two parts:

- **System prompt** = the rubric (`prompts/scorer/v2.md`), static per version: who the owner is,
  the 1–10 criteria, skip rules, message rules, and the JSON output schema. Versioned so eval
  results tie to the exact prompt (`PROMPT_VERSION` is logged on every `llm_calls` row).
- **User message** = the dynamic post, built as:
  ```
  Post title: {title}
  Post body:  {compressed_body}
  Recent messages sent (vary from these): {last 5 drafts}
  ```

So the context is deliberately composed: **rubric (instructions) + title + compressed body (data)
+ recent drafts (for anti-bot variation)** — nothing else.

## What we compress, and why

Reddit post bodies run **10k–40k characters** (we've seen 37k). Sent raw, that:
- wastes tokens and latency on every call,
- enlarges the **prompt-injection surface** (more attacker-controlled text), and
- dilutes the hiring signal in a wall of boilerplate.

`scorer._compress_body()` (heuristic, **no extra LLM call**):
1. **Collapse whitespace** — newlines/tabs/runs of spaces → single spaces.
2. **Mask URLs** → `[link]` — the scorer doesn't need the raw URL (just that an apply link exists),
   and raw URLs are a token + injection cost. (The actual links are extracted separately for the
   "apply here" surfacing, from the *original* body — not this compressed copy.)
3. **Cap to ~2.5k chars, keeping head + tail** — hiring intent/requirements cluster at the top,
   budget/contact at the bottom; the middle is usually filler. Bodies under the cap pass through
   untouched.

## The recent-drafts window

The last 5 sent drafts are appended so the model can **vary** new drafts (anti-bot). Capped at 5 to
bound tokens while still giving enough signal to avoid repetition.

## How it was tested

- **Unit:** a 29k-char body compresses to ~2.5k with the cap, head and tail preserved (intro +
  "BUDGET $5000, apply at [link]" both survive); short bodies unchanged; URLs masked; empty → "".
- **No-regression (after golden labeling):** re-run the eval harness with compression on vs off on a
  sample — scores must not move materially while token/cost per call drops.
