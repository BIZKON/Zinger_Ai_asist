"""Claude API + каскадный роутинг LLM.

Каскад:
  - simple (intent detection) → Gemini Flash (бесплатно)
  - medium (обычный диалог)  → Claude Haiku
  - complex (сложные задачи) → Claude Sonnet
"""

import time

import httpx
import structlog
from anthropic import AsyncAnthropic

from bot.config import settings

logger = structlog.get_logger()

_anthropic: AsyncAnthropic | None = None


def _get_anthropic() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic


async def chat(
    messages: list[dict],
    system_prompt: str = "",
    complexity: str = "auto",
    max_tokens: int = 1024,
) -> str:
    """Main LLM entry point with cascading routing.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."}.
        system_prompt: System prompt (persona + context).
        complexity: "simple" | "medium" | "complex" | "auto".
        max_tokens: Max response tokens.

    Returns:
        LLM response text.
    """
    if complexity == "auto":
        complexity = _detect_complexity(messages)

    if complexity == "simple" and settings.gemini_api_key:
        return await _gemini_flash(messages, system_prompt, max_tokens)
    elif complexity == "medium":
        return await _claude(messages, system_prompt, max_tokens, model="claude-haiku-4-5-20251001")
    else:
        return await _claude(messages, system_prompt, max_tokens, model="claude-sonnet-4-5-20250514")


def _detect_complexity(messages: list[dict]) -> str:
    """Simple heuristic to detect message complexity."""
    if not messages:
        return "medium"

    last_msg = messages[-1].get("content", "")
    word_count = len(last_msg.split())

    # Short messages — simple intent detection
    if word_count <= 5:
        return "simple"
    # Medium length — regular dialog
    elif word_count <= 50:
        return "medium"
    # Long messages — complex tasks
    else:
        return "complex"


async def _claude(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    model: str,
) -> str:
    """Call Anthropic Claude API."""
    client = _get_anthropic()
    start = time.monotonic()

    try:
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        elapsed = time.monotonic() - start

        text = response.content[0].text if response.content else ""
        usage = response.usage

        logger.info(
            "llm_call",
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            elapsed_sec=round(elapsed, 2),
        )
        return text

    except Exception as e:
        logger.error("llm_error", model=model, error=str(e))
        # Fallback: try the other Claude model
        if "haiku" in model:
            return await _claude(messages, system_prompt, max_tokens, "claude-sonnet-4-5-20250514")
        return "Извини, что-то пошло не так с ИИ. Попробуй ещё раз."


async def _gemini_flash(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
) -> str:
    """Call Google Gemini Flash via REST API (free tier)."""
    start = time.monotonic()

    try:
        # Build Gemini-format messages
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        logger.info("llm_call", model="gemini-flash", elapsed_sec=round(elapsed, 2))
        return text

    except Exception as e:
        logger.warning("gemini_fallback", error=str(e))
        # Fallback to Claude Haiku
        return await _claude(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")


async def extract_json(
    prompt: str,
    system_prompt: str = "Respond with valid JSON only. No markdown, no explanation.",
    max_tokens: int = 512,
) -> str:
    """Call LLM expecting a JSON response (for fact extraction, intent detection, etc.)."""
    messages = [{"role": "user", "content": prompt}]
    return await _claude(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")
