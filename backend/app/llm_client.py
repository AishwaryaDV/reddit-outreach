"""Single chokepoint for every LLM call (score / draft / judge).

Backends:
  - claude_sdk: primary, via the Claude Code subscription login (no API key).
  - gemini: fallback / overflow, free tier.

Protects the Claude Pro subscription by rate-budgeting Claude: when the budget
for the current minute or hour is used up, scoring overflows to Gemini
*immediately* (no waiting, no backlog) so a time-sensitive post is never missed.
Every call is logged to the llm_calls table. LLM_MODE=replay serves recorded
responses from evals/cache/ so evals and demos cost nothing and need no accounts.
"""
import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.config import (
    CLAUDE_MAX_BUDGET_USD, CLAUDE_MAX_PER_HOUR, CLAUDE_MAX_PER_MIN,
    CLAUDE_MODEL, GEMINI_API_KEY, GEMINI_FALLBACK_MODELS, GEMINI_MODEL, LLM_MODE,
)
from app.db import get_session_factory
from app.models import LLMCall

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[2] / "evals" / "cache"


@dataclass
class LLMResult:
    text: str
    backend: str  # claude_sdk | gemini | replay
    model: str
    fell_back: bool
    latency_ms: int
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


def _cache_key(step: str, system_prompt: str, user_message: str) -> str:
    h = hashlib.sha256(f"{step}\x00{system_prompt}\x00{user_message}".encode())
    return h.hexdigest()[:24]


def _read_cache(key: str) -> str | None:
    f = _CACHE_DIR / f"{key}.txt"
    return f.read_text() if f.exists() else None


def _write_cache(key: str, text: str) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (_CACHE_DIR / f"{key}.txt").write_text(text)
    except Exception:
        pass  # caching is best-effort


def _tok(usage, *names):
    for n in names:
        if isinstance(usage, dict) and usage.get(n) is not None:
            return usage[n]
        v = getattr(usage, n, None)
        if v is not None:
            return v
    return None


async def _claude_budget_available() -> bool:
    """True if we're under the per-minute AND per-hour Claude call budget.
    This is a routing decision (Claude vs Gemini), never a wait."""
    now = datetime.now(tz=timezone.utc)
    async with get_session_factory()() as session:
        per_min = await session.scalar(
            select(func.count(LLMCall.id)).where(
                LLMCall.backend == "claude_sdk",
                LLMCall.created_at >= now - timedelta(minutes=1),
            )
        )
        if (per_min or 0) >= CLAUDE_MAX_PER_MIN:
            return False
        per_hour = await session.scalar(
            select(func.count(LLMCall.id)).where(
                LLMCall.backend == "claude_sdk",
                LLMCall.created_at >= now - timedelta(hours=1),
            )
        )
        return (per_hour or 0) < CLAUDE_MAX_PER_HOUR


async def _call_claude(system_prompt: str, user_message: str) -> LLMResult:
    from claude_agent_sdk import (
        AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query,
    )
    options = ClaudeAgentOptions(
        model=CLAUDE_MODEL,
        system_prompt=system_prompt,
        max_turns=1,
        allowed_tools=[],
        max_budget_usd=CLAUDE_MAX_BUDGET_USD,  # native per-call cost cap
    )
    text, cost, in_tok, out_tok = "", None, None, None
    start = time.monotonic()
    async for message in query(prompt=user_message, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text += block.text
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd
            in_tok = _tok(message.usage, "input_tokens", "prompt_tokens")
            out_tok = _tok(message.usage, "output_tokens", "completion_tokens")
    latency = int((time.monotonic() - start) * 1000)
    return LLMResult(
        text=text, backend="claude_sdk", model=CLAUDE_MODEL, fell_back=False,
        latency_ms=latency, cost_usd=cost, input_tokens=in_tok, output_tokens=out_tok,
    )


_genai_client = None


def _gemini():
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


def _gemini_models() -> list[str]:
    extra = [m.strip() for m in GEMINI_FALLBACK_MODELS.split(",") if m.strip()]
    return [GEMINI_MODEL, *extra]


# Substrings that mark a retryable/transient Gemini error.
_TRANSIENT = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL", "deadline", "timeout")


async def _call_gemini(system_prompt: str, user_message: str, fell_back: bool) -> LLMResult:
    from google.genai import types
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
    )
    last_err = None
    for model in _gemini_models():
        for attempt in range(2):  # one retry per model on transient errors
            start = time.monotonic()
            try:
                resp = await _gemini().aio.models.generate_content(
                    model=model, contents=user_message, config=config,
                )
                latency = int((time.monotonic() - start) * 1000)
                um = getattr(resp, "usage_metadata", None)
                return LLMResult(
                    text=resp.text or "", backend="gemini", model=model, fell_back=fell_back,
                    latency_ms=latency, cost_usd=0.0,
                    input_tokens=_tok(um, "prompt_token_count"),
                    output_tokens=_tok(um, "candidates_token_count"),
                )
            except Exception as e:
                last_err = e
                transient = any(t in str(e) for t in _TRANSIENT)
                if transient and attempt == 0:
                    await asyncio.sleep(1.5)
                    continue
                break  # non-transient, or already retried — try the next model
    raise last_err if last_err else RuntimeError("gemini: all models failed")


async def complete(step: str, system_prompt: str, user_message: str) -> LLMResult:
    """One model call for `step`. Claude primary within its rate budget, Gemini
    overflow/fallback (immediate — never waits). Raises only on a replay cache miss."""
    key = _cache_key(step, system_prompt, user_message)

    if LLM_MODE == "replay":
        cached = _read_cache(key)
        if cached is None:
            raise RuntimeError(f"replay: no cached response for step={step} key={key}")
        return LLMResult(text=cached, backend="replay", model="replay", fell_back=False, latency_ms=0, cost_usd=0.0)

    result = None
    tried_claude = await _claude_budget_available()
    if tried_claude:
        try:
            result = await _call_claude(system_prompt, user_message)
        except Exception as e:
            logger.warning("Claude call failed (%s) — overflowing to Gemini", str(e)[:150])
            result = None
    if result is None:
        try:
            result = await _call_gemini(system_prompt, user_message, fell_back=tried_claude)
        except Exception as e:
            logger.error("Gemini call failed: %s", str(e)[:200])
            return LLMResult(
                text="", backend="gemini", model=GEMINI_MODEL, fell_back=tried_claude,
                latency_ms=0, cost_usd=0.0, error=str(e)[:500],
            )

    if result.text:
        _write_cache(key, result.text)
    return result


async def log_call(step: str, result: LLMResult, post_id: str | None, prompt_version: str | None, parse_ok: bool) -> None:
    try:
        async with get_session_factory()() as session:
            session.add(LLMCall(
                post_id=uuid.UUID(str(post_id)) if post_id else None,
                step=step, model=result.model, backend=result.backend, fell_back=result.fell_back,
                prompt_version=prompt_version, input_tokens=result.input_tokens,
                output_tokens=result.output_tokens, cost_usd=result.cost_usd,
                latency_ms=result.latency_ms, parse_ok=parse_ok, error=result.error,
            ))
            await session.commit()
    except Exception as e:
        logger.error("Failed to log llm_call: %s", str(e)[:200])
