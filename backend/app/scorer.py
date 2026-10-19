import json
import re
import logging
from functools import lru_cache
from pathlib import Path

from app.config import PORTFOLIO_URL, LLM_MODE
from app.database import get_setting
from app.llm_client import complete, log_call

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"
# Reported by GET /status.
SCORER_MODE = "replay" if LLM_MODE == "replay" else "claude_sdk+gemini"

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "scorer"


async def _get_portfolio_url():
    return await get_setting("portfolio_url", PORTFOLIO_URL)


@lru_cache
def _load_prompt_template(version: str) -> str:
    return (_PROMPTS_DIR / f"{version}.md").read_text()


async def _build_system_prompt() -> str:
    return _load_prompt_template(PROMPT_VERSION).format(portfolio_url=await _get_portfolio_url())


async def score_and_draft(title: str, body: str, recent_drafts: list[str] | None = None) -> dict | None:
    """Score a post 1-10 and draft a DM. Routes through llm_client (Claude
    primary within its rate budget, Gemini overflow) so it can never drain the
    Claude Pro subscription. Returns the parsed result, or None if scoring is
    paused or the response can't be parsed."""
    # Kill switch — pause all LLM scoring instantly from Settings, no redeploy.
    if (await get_setting("scoring_enabled", "true")) != "true":
        logger.info("Scoring paused (scoring_enabled=false) — skipping")
        return None

    system_prompt = await _build_system_prompt()
    recent_context = ""
    if recent_drafts:
        recent_context = "\n\nRecent messages sent (vary from these):\n" + "\n---\n".join(recent_drafts)
    user_message = f"Post title: {title}\n\nPost body: {body or '(no body)'}{recent_context}"

    result = await complete("score", system_prompt, user_message)
    parsed = _extract_and_validate(result.text) if result.text else None
    await log_call("score", result, None, PROMPT_VERSION, parse_ok=parsed is not None)
    if parsed is None:
        logger.warning(
            "Scorer: unparseable %s response%s",
            result.backend, f" ({result.error})" if result.error else "",
        )
    return parsed


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
