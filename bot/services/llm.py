"""Каскадный роутинг LLM.

Приоритет:
  1. OpenAI GPT-4o (основной, если есть ключ)
  2. Anthropic Claude (fallback)
  3. Gemini Flash (для простых интентов, бесплатно)

Каскад по сложности:
  - simple → Gemini Flash / GPT-4o-mini
  - medium → GPT-4o / Claude Haiku
  - complex → GPT-4o / Claude Sonnet
"""

import time

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()


async def chat(
    messages: list[dict],
    system_prompt: str = "",
    complexity: str = "auto",
    max_tokens: int = 1024,
) -> str:
    """Main LLM entry point with cascading routing."""
    if complexity == "auto":
        complexity = _detect_complexity(messages)

    # Try Gemini Flash for simple tasks (free)
    if complexity == "simple" and settings.gemini_api_key:
        return await _gemini_flash(messages, system_prompt, max_tokens)

    # Primary: OpenAI
    if settings.openai_api_key:
        model = "gpt-4o-mini" if complexity == "simple" else "gpt-4o"
        return await _openai(messages, system_prompt, max_tokens, model)

    # Fallback: Anthropic Claude
    if settings.anthropic_api_key:
        model = (
            "claude-haiku-4-5-20251001" if complexity == "medium"
            else "claude-sonnet-4-5-20250514"
        )
        return await _claude(messages, system_prompt, max_tokens, model)

    return "Ни один LLM API не настроен. Добавь OPENAI_API_KEY или ANTHROPIC_API_KEY в .env"


def _detect_complexity(messages: list[dict]) -> str:
    if not messages:
        return "medium"
    last_msg = messages[-1].get("content", "")
    word_count = len(last_msg.split())
    if word_count <= 5:
        return "simple"
    elif word_count <= 50:
        return "medium"
    return "complex"


# ── OpenAI ──

async def _openai(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    model: str,
) -> str:
    """Call OpenAI ChatCompletion API."""
    start = time.monotonic()

    try:
        oai_messages = []
        if system_prompt:
            oai_messages.append({"role": "system", "content": system_prompt})
        oai_messages.extend(messages)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": oai_messages,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        logger.info(
            "llm_call",
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            elapsed_sec=round(elapsed, 2),
        )
        return text

    except Exception as e:
        logger.error("openai_error", model=model, error=str(e))
        # Fallback to Claude if available
        if settings.anthropic_api_key:
            logger.info("falling_back_to_claude")
            return await _claude(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")
        return "Ошибка при обращении к ИИ. Попробуй ещё раз."


# ── Anthropic Claude ──

async def _claude(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    model: str,
) -> str:
    """Call Anthropic Claude API."""
    start = time.monotonic()

    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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
        logger.error("claude_error", model=model, error=str(e))
        return "Ошибка при обращении к ИИ. Попробуй ещё раз."


# ── Gemini Flash ──

async def _gemini_flash(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
) -> str:
    """Call Google Gemini Flash via REST API (free tier)."""
    start = time.monotonic()

    try:
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
        # Fallback to primary
        if settings.openai_api_key:
            return await _openai(messages, system_prompt, max_tokens, "gpt-4o-mini")
        if settings.anthropic_api_key:
            return await _claude(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")
        return "Ошибка Gemini и нет fallback."


# ── Utility ──

async def extract_json(
    prompt: str,
    system_prompt: str = "Respond with valid JSON only. No markdown, no explanation.",
    max_tokens: int = 512,
) -> str:
    """Call LLM expecting a JSON response."""
    messages = [{"role": "user", "content": prompt}]

    if settings.openai_api_key:
        return await _openai(messages, system_prompt, max_tokens, "gpt-4o-mini")
    if settings.anthropic_api_key:
        return await _claude(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")
    return "[]"
