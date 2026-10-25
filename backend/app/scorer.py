import json
import re
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.config import PORTFOLIO_URL, LLM_MODE, TRIAGE_SKIP_CONFIDENCE
from app.database import get_setting
from app.llm_client import complete, log_call, quota_exceeded
from app.guardrails import enforce_url_allowlist, wrap_untrusted
from app.schemas import ScoreResult, TriageResult, JudgeResult

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v3"
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


def _extract_json(text: str) -> dict | None:
    """Pull a JSON object out of the response (handles code fences / stray text)."""
    if not text:
        return None
    for candidate in (text.strip(), re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _validate(text: str) -> tuple[ScoreResult | None, str | None]:
    data = _extract_json(text)
    if data is None:
        return None, "no JSON object found"
    try:
        return ScoreResult.model_validate(data), None
    except ValidationError as e:
        return None, "; ".join(err["msg"] for err in e.errors())[:200]


# Context engineering — the scorer prompt doesn't need raw 10k-40k-char bodies.
# Bound the body (keep head + tail, where hiring details cluster), collapse
# whitespace, and mask URLs (not needed to score, and a token/injection cost).
BODY_CHAR_CAP = 2500
_URL_RE = re.compile(r"https?://\S+")


def _compress_body(body: str | None, cap: int = BODY_CHAR_CAP) -> str:
    if not body:
        return ""
    text = _URL_RE.sub("[link]", re.sub(r"\s+", " ", body)).strip()
    if len(text) <= cap:
        return text
    head = cap * 2 // 3
    return text[:head].rstrip() + " […] " + text[-(cap - head):].lstrip()


@lru_cache
def _load_triage_prompt() -> str:
    return (_PROMPTS_DIR.parent / "triage" / "v1.md").read_text()


def _validate_triage(text: str) -> TriageResult | None:
    data = _extract_json(text)
    if data is None:
        return None
    try:
        return TriageResult.model_validate(data)
    except ValidationError:
        return None


async def triage(title: str, body: str) -> tuple[bool, float]:
    """Cheap first-pass: is this plausibly a real paid dev-hire? Returns
    (is_hire, confidence). On any failure returns (True, 0.0) so the post falls
    through to the deep score — we never drop a post on a triage error."""
    user_message = wrap_untrusted(title, _compress_body(body))
    result = await complete("triage", _load_triage_prompt(), user_message, schema=TriageResult)
    tr = _validate_triage(result.text)
    await log_call("triage", result, None, "triage-v1", parse_ok=tr is not None)
    if tr is None:
        return True, 0.0
    return tr.decision == "hire", tr.confidence


@lru_cache
def _load_judge_prompt() -> str:
    return (_PROMPTS_DIR.parent / "judge" / "v1.md").read_text()


@lru_cache
def _load_profile() -> str:
    p = _PROMPTS_DIR.parent.parent / "profile.yaml"
    return p.read_text() if p.exists() else ""


def _validate_judge(text: str) -> JudgeResult | None:
    data = _extract_json(text)
    if data is None:
        return None
    try:
        return JudgeResult.model_validate(data)
    except ValidationError:
        return None


async def judge_draft(title: str, draft: str) -> JudgeResult:
    """Grade a drafted DM against the rules. Fail-closed: any error → FAILED
    (hard-block), since sending a bad DM is worse than withholding one."""
    user_message = (
        f"OWNER FACTS (the draft must not claim anything outside these):\n{_load_profile()}\n\n"
        f"POST TITLE: {title}\n\nDRAFTED DM:\n{draft}"
    )
    result = await complete("judge", _load_judge_prompt(), user_message, schema=JudgeResult, prefer_cheap=True)
    jr = _validate_judge(result.text)
    await log_call("judge", result, None, "judge-v1", parse_ok=jr is not None)
    if jr is None:
        return JudgeResult(passed=False, reasons=["judge could not evaluate the draft"])
    return jr


async def score_and_draft(title: str, body: str, recent_drafts: list[str] | None = None) -> dict | None:
    """Score a post and draft a DM, validated against the ScoreResult schema.

    Routes through llm_client (Claude primary, rate-budgeted; Gemini overflow) so
    it can never drain the Pro subscription. Returns a dict with score/reason/draft
    (+ the structured fields), or None if scoring is paused or validation fails.
    """
    # Kill switch — pause all LLM scoring instantly from Settings, no redeploy.
    if (await get_setting("scoring_enabled", "true")) != "true":
        logger.info("Scoring paused (scoring_enabled=false) — skipping")
        return None
    if await quota_exceeded():
        logger.warning("Daily LLM quota reached — scoring paused for today")
        return None

    # Difficulty routing — cheap triage first. A CONFIDENT "not a hire" still gets a
    # full rubric score, just on cheap Gemini (route, don't drop — so a wrong triage
    # can't silently kill a lead); only triaged-in posts spend the strong Claude tier.
    is_hire, conf = await triage(title, body)
    triaged_out = not is_hire and conf >= TRIAGE_SKIP_CONFIDENCE
    if triaged_out:
        logger.info("Triaged out (not_hire, conf=%.2f) — full score on cheap tier", conf)

    system_prompt = await _build_system_prompt()
    recent_context = ""
    if recent_drafts:
        recent_context = "\n\nRecent messages sent (vary from these):\n" + "\n---\n".join(recent_drafts)
    user_message = wrap_untrusted(title, _compress_body(body)) + recent_context

    result = await complete("score", system_prompt, user_message, schema=ScoreResult, prefer_cheap=triaged_out)
    sr, err = _validate(result.text)

    # Retry once with the validation error appended — let the model self-correct.
    if sr is None and result.text:
        retry_message = (
            f"{user_message}\n\nYour previous reply was invalid ({err}). "
            "Return ONLY valid JSON with the required fields."
        )
        result = await complete("score", system_prompt, retry_message, schema=ScoreResult, prefer_cheap=triaged_out)
        sr, err = _validate(result.text)

    await log_call("score", result, None, PROMPT_VERSION, parse_ok=sr is not None)
    if sr is None:
        logger.warning("Scorer: invalid response via %s (%s)", result.backend, err or result.error)
        return None

    draft = sr.draft if sr.score > 2 else ""
    reason = "; ".join(sr.reasons) or ("; ".join(sr.red_flags) if sr.red_flags else "")

    # Guardrails on the draft: output URL allowlist + LLM-judge hard-block.
    if draft:
        draft, url_violation = enforce_url_allowlist(draft, await _get_portfolio_url())
        verdict = await judge_draft(title, draft)
        if not verdict.passed:
            logger.info("Draft failed judge — withholding: %s", "; ".join(verdict.reasons)[:100])
            reason = (reason + " | draft withheld (judge): " + "; ".join(verdict.reasons)).strip(" |")
            draft = ""
        elif url_violation:
            reason = (reason + " | stripped a non-portfolio link from the draft").strip(" |")

    return {
        "score": sr.score,
        "reason": reason,
        "draft": draft,
        "label": sr.label,
        "red_flags": sr.red_flags,
        "budget_mentioned": sr.budget_mentioned,
    }
