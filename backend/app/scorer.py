import json
import re
import logging
from app.config import PORTFOLIO_URL
from app.database import get_setting

logger = logging.getLogger(__name__)

# Reported by GET /status. Flip to "claude-haiku-4-5" when the real scorer
# below is enabled, so the dashboard reflects what's actually running.
SCORER_MODE = "mock"


async def _get_portfolio_url():
    return await get_setting("portfolio_url", PORTFOLIO_URL)


SYSTEM_PROMPT_TEMPLATE = """You are a filter for a personal Reddit job outreach tool. The owner is a freelance fullstack developer (3 years experience, React specialist, also does Node/backend, MVP builds, web apps).

Your job: read a Reddit post and decide if it's worth reaching out to, score it, and if so — write a short personalized DM.

---

SCORING (return an integer 1-10):

8-10 STRONG MATCH — show in dashboard, high priority
- Clear hire intent from a real person (founder, startup, small business owner, individual)
- Post has a proper body describing the project or what they need built
- Mentions specific requirements (tech stack, features, timeline, MVP, etc.)
- Remote-friendly or doesn't restrict location
- Budget mentioned or implied (even rough is fine)
- Asks for portfolio, experience, or to get in touch

5-7 POSSIBLE MATCH — show in dashboard, normal priority
- Some signals missing but genuine hire intent is there
- Post is real but vague on details
- Worth showing to the user to decide

3-4 WEAK MATCH — show in dashboard, low priority
- Borderline — might be worth reaching out, might not
- User will decide

1-2 SKIP — discard silently, never show
Apply this to ALL of the following:
- Scam posts: vague about the actual work, only mentions stack + asks for availability, "paying $X DM me" with no project details, too-good-to-be-true rates ($5000/week part time), asks to contact via Telegram/WhatsApp/external email immediately, mentions Upwork/Fiverr/Freelancer referral links, crypto/NFT/blockchain payment only, poor grammar + vague promises
- [For Hire] posts — someone selling their own skills, NOT hiring
- Sad story posts — someone asking for job help or venting
- Job board reposts — company HR posts
- Advice-seeking posts — "how do I find a developer?" with no actual hire intent
- Looking for co-founders only
- Posts requiring in-office attendance or specific country residency (e.g. "must be US-based")
- Posts requiring tech stacks completely outside web/fullstack (embedded systems, ML research, etc.)
- Budget explicitly under $200 for a full project
- No body at all — just a title with no description

---

MESSAGE RULES (only write a draft for score >= 3):

Structure — exactly 3 lines, no more:
Line 1: Hook — references their specific post, matches their tone
Line 2: Value prop — highlight the most relevant skill/experience based on what they need
Line 3: Portfolio — ALWAYS the last line, ALWAYS included, no exceptions

Tone rules:
- Casual post → casual message. Formal post → slightly more polished but still conversational
- Never sound like a cover letter
- Never mention rates or availability in the first message
- Keep it short — 2-3 lines, never more

Anti-bot variation (IMPORTANT):
You will receive the last few messages sent as context. Ensure your new draft is meaningfully different in wording, structure, and tone from those recent messages. Rotate:
- Hook openers: "Saw your post", "This looks like a great fit", "Right up my alley", "Came across your post", "React dev here", etc.
- Portfolio CTAs: "Here's my portfolio", "Checkout my portfolio", "My work", "My portfolio", "See my work at", etc.

Portfolio URL is always: {portfolio_url}

---

Return ONLY valid JSON in this exact format, no other text:
{{
  "score": <integer 1-10>,
  "reason": "<one sentence explaining the score>",
  "draft": "<the message draft, or empty string if score <= 2>"
}}"""


async def _build_system_prompt():
    return SYSTEM_PROMPT_TEMPLATE.format(portfolio_url=await _get_portfolio_url())


async def score_and_draft(title: str, body: str, recent_drafts: list[str] | None = None) -> dict | None:
    # MOCK — swap back to real scorer once Claude quota resets
    portfolio_url = await _get_portfolio_url()
    return {
        "score": 7,
        "reason": "Mock score for pipeline testing — real scorer disabled",
        "draft": f"Saw your post and this looks right up my alley. I build React apps and MVPs for founders and small teams — here's my work: {portfolio_url}",
    }

    # --- REAL SCORER (re-enable when ready) ---
    # from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
    #
    # recent_context = ""
    # if recent_drafts:
    #     recent_context = "\n\nRecent messages sent (vary from these):\n" + "\n---\n".join(recent_drafts)
    #
    # user_message = f"Post title: {title}\n\nPost body: {body or '(no body)'}{recent_context}"
    #
    # options = ClaudeAgentOptions(
    #     model="claude-haiku-4-5-20251001",
    #     system_prompt=await _build_system_prompt(),
    #     max_turns=1,
    #     allowed_tools=[],
    # )
    #
    # try:
    #     text = ""
    #     async for message in query(prompt=user_message, options=options):
    #         if isinstance(message, AssistantMessage):
    #             for block in message.content:
    #                 if isinstance(block, TextBlock):
    #                     text += block.text
    #
    #     if not text:
    #         logger.warning("Agent SDK returned empty response")
    #         return None
    #
    #     return _extract_and_validate(text)
    # except Exception as e:
    #     logger.error("Scorer error: %s", e)
    #     return None


def _extract_and_validate(text: str) -> dict | None:
    # Try 1: direct parse
    data = _try_parse(text.strip())

    # Try 2: strip markdown code fences
    if data is None:
        stripped = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
        data = _try_parse(stripped)

    # Try 3: find first {...} block containing "score"
    if data is None:
        match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
        if match:
            data = _try_parse(match.group())

    if data is None:
        logger.error("Could not extract JSON from scorer response | raw: %s", text[:300])
        return None

    # Validate required fields and types
    score = data.get("score")
    if not isinstance(score, int) or not (1 <= score <= 10):
        logger.error("Invalid score value: %s", score)
        return None

    data.setdefault("reason", "")
    data.setdefault("draft", "")

    # Enforce: no draft for low scores
    if score <= 2:
        data["draft"] = ""

    return data


def _try_parse(text: str) -> dict | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
