"""Каскадный роутинг LLM.

Приоритет (для РФ-развёртывания):
  1. YandexGPT (основной, работает из РФ без ограничений)
  2. OpenAI GPT-4o (если доступен из региона)
  3. Anthropic Claude (fallback, если доступен)
  4. Gemini Flash (для простых интентов, бесплатно)

Каскад по сложности:
  - simple → yandexgpt-lite / Gemini Flash / GPT-4o-mini
  - medium → yandexgpt / GPT-4o / Claude Haiku
  - complex → yandexgpt / GPT-4o / Claude Sonnet
"""

import time
from typing import NamedTuple

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()


class LLMResult(NamedTuple):
    """Return type for chat_with_usage — includes token counts."""
    text: str
    model: str
    input_tokens: int
    output_tokens: int


async def chat(
    messages: list[dict],
    system_prompt: str = "",
    complexity: str = "auto",
    max_tokens: int = 1024,
) -> str:
    """Main LLM entry point with cascading routing."""
    if complexity == "auto":
        complexity = _detect_complexity(messages)

    # Primary (для РФ): YandexGPT
    if settings.yandex_gpt_api_key and settings.yandex_gpt_folder_id:
        model = "yandexgpt-lite" if complexity == "simple" else "yandexgpt"
        return await _yandex_gpt(messages, system_prompt, max_tokens, model)

    # Try Gemini Flash for simple tasks (free, если доступен)
    if complexity == "simple" and settings.gemini_api_key:
        return await _gemini_flash(messages, system_prompt, max_tokens)

    # Fallback: OpenAI (если регион поддерживает)
    if settings.openai_api_key:
        model = "gpt-4o-mini" if complexity == "simple" else "gpt-4o"
        return await _openai(messages, system_prompt, max_tokens, model)

    # Fallback: Anthropic Claude (если регион поддерживает)
    if settings.anthropic_api_key:
        model = (
            "claude-haiku-4-5-20251001" if complexity == "medium"
            else "claude-sonnet-4-5-20250514"
        )
        return await _claude(messages, system_prompt, max_tokens, model)

    return "Ни один LLM API не настроен. Добавь YANDEX_GPT_API_KEY в .env"


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


async def chat_with_usage(
    messages: list[dict],
    system_prompt: str = "",
    complexity: str = "auto",
    max_tokens: int = 1024,
) -> LLMResult:
    """Like chat(), but returns LLMResult with token counts."""
    if complexity == "auto":
        complexity = _detect_complexity(messages)

    # Primary (для РФ): YandexGPT
    if settings.yandex_gpt_api_key and settings.yandex_gpt_folder_id:
        model = "yandexgpt-lite" if complexity == "simple" else "yandexgpt"
        return await _yandex_gpt_usage(messages, system_prompt, max_tokens, model)

    if complexity == "simple" and settings.gemini_api_key:
        return await _gemini_flash_usage(messages, system_prompt, max_tokens)

    if settings.openai_api_key:
        model = "gpt-4o-mini" if complexity == "simple" else "gpt-4o"
        return await _openai_usage(messages, system_prompt, max_tokens, model)

    if settings.anthropic_api_key:
        model = (
            "claude-haiku-4-5-20251001" if complexity == "medium"
            else "claude-sonnet-4-5-20250514"
        )
        return await _claude_usage(messages, system_prompt, max_tokens, model)

    return LLMResult("Ни один LLM API не настроен.", "none", 0, 0)


async def _openai_usage(
    messages: list[dict], system_prompt: str, max_tokens: int, model: str,
) -> LLMResult:
    """OpenAI call returning LLMResult."""
    t0 = time.monotonic()
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
                json={"model": model, "messages": oai_messages, "max_tokens": max_tokens},
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)
        logger.info("llm_call", model=model, input_tokens=inp, output_tokens=out,
                     elapsed_sec=round(time.monotonic() - t0, 2))
        return LLMResult(text, model, inp, out)
    except Exception as e:
        logger.error("openai_usage_error", model=model, error=str(e))
        if settings.anthropic_api_key:
            return await _claude_usage(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")
        return LLMResult("Ошибка при обращении к ИИ.", model, 0, 0)


async def _claude_usage(
    messages: list[dict], system_prompt: str, max_tokens: int, model: str,
) -> LLMResult:
    """Claude call returning LLMResult."""
    t0 = time.monotonic()
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await client.messages.create(**kwargs)
        text = response.content[0].text if response.content else ""
        inp = response.usage.input_tokens
        out = response.usage.output_tokens
        logger.info("llm_call", model=model, input_tokens=inp, output_tokens=out,
                     elapsed_sec=round(time.monotonic() - t0, 2))
        return LLMResult(text, model, inp, out)
    except Exception as e:
        logger.error("claude_usage_error", model=model, error=str(e))
        return LLMResult("Ошибка при обращении к ИИ.", model, 0, 0)


async def _gemini_flash_usage(
    messages: list[dict], system_prompt: str, max_tokens: int,
) -> LLMResult:
    """Gemini Flash call returning LLMResult (tokens estimated as 0 — free tier)."""
    text = await _gemini_flash(messages, system_prompt, max_tokens)
    return LLMResult(text, "gemini-flash", 0, 0)


# ── YandexGPT (основной для РФ) ──

_YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def _yandex_model_uri(model: str) -> str:
    """Build modelUri: gpt://<folder_id>/<model>/latest."""
    return f"gpt://{settings.yandex_gpt_folder_id}/{model}/latest"


def _yandex_messages(messages: list[dict], system_prompt: str) -> list[dict]:
    """Convert OpenAI-style messages to YandexGPT format (text instead of content)."""
    result = []
    if system_prompt:
        result.append({"role": "system", "text": system_prompt})
    for msg in messages:
        result.append({
            "role": msg.get("role", "user"),
            "text": msg.get("content", ""),
        })
    return result


async def _yandex_gpt(
    messages: list[dict], system_prompt: str, max_tokens: int, model: str,
) -> str:
    """Call YandexGPT Foundation Models API."""
    t0 = time.monotonic()
    try:
        payload = {
            "modelUri": _yandex_model_uri(model),
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": str(max_tokens),
            },
            "messages": _yandex_messages(messages, system_prompt),
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _YANDEX_GPT_URL,
                headers={
                    "Authorization": f"Api-Key {settings.yandex_gpt_api_key}",
                    "Content-Type": "application/json",
                    "x-folder-id": settings.yandex_gpt_folder_id,
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        alternatives = data.get("result", {}).get("alternatives", [])
        text = alternatives[0].get("message", {}).get("text", "") if alternatives else ""
        usage = data.get("result", {}).get("usage", {})

        logger.info(
            "llm_call",
            model=model,
            input_tokens=int(usage.get("inputTextTokens", 0)),
            output_tokens=int(usage.get("completionTokens", 0)),
            elapsed_sec=round(time.monotonic() - t0, 2),
        )
        return text
    except Exception as e:
        logger.error("yandex_gpt_error", model=model, error=str(e))
        # Fallback cascade: Gemini → OpenAI → Claude
        if settings.gemini_api_key:
            return await _gemini_flash(messages, system_prompt, max_tokens)
        if settings.openai_api_key:
            return await _openai(messages, system_prompt, max_tokens, "gpt-4o-mini")
        return "Ошибка при обращении к ИИ. Попробуй ещё раз."


async def _yandex_gpt_usage(
    messages: list[dict], system_prompt: str, max_tokens: int, model: str,
) -> LLMResult:
    """YandexGPT call returning LLMResult with token counts."""
    t0 = time.monotonic()
    try:
        payload = {
            "modelUri": _yandex_model_uri(model),
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": str(max_tokens),
            },
            "messages": _yandex_messages(messages, system_prompt),
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _YANDEX_GPT_URL,
                headers={
                    "Authorization": f"Api-Key {settings.yandex_gpt_api_key}",
                    "Content-Type": "application/json",
                    "x-folder-id": settings.yandex_gpt_folder_id,
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        alternatives = data.get("result", {}).get("alternatives", [])
        text = alternatives[0].get("message", {}).get("text", "") if alternatives else ""
        usage = data.get("result", {}).get("usage", {})
        inp = int(usage.get("inputTextTokens", 0))
        out = int(usage.get("completionTokens", 0))

        logger.info("llm_call", model=model, input_tokens=inp, output_tokens=out,
                     elapsed_sec=round(time.monotonic() - t0, 2))
        return LLMResult(text, model, inp, out)
    except Exception as e:
        logger.error("yandex_gpt_usage_error", model=model, error=str(e))
        return LLMResult("Ошибка при обращении к ИИ.", model, 0, 0)


# ── Utility ──

async def extract_json(
    prompt: str,
    system_prompt: str = "Respond with valid JSON only. No markdown, no explanation.",
    max_tokens: int = 512,
) -> str:
    """Call LLM expecting a JSON response."""
    messages = [{"role": "user", "content": prompt}]

    # Primary для РФ: YandexGPT (lite для JSON-извлечения достаточно)
    if settings.yandex_gpt_api_key and settings.yandex_gpt_folder_id:
        return await _yandex_gpt(messages, system_prompt, max_tokens, "yandexgpt-lite")
    if settings.openai_api_key:
        return await _openai(messages, system_prompt, max_tokens, "gpt-4o-mini")
    if settings.anthropic_api_key:
        return await _claude(messages, system_prompt, max_tokens, "claude-haiku-4-5-20251001")
    return "[]"
