"""Perplexity Sonar API — каскадный поиск.

Каскад по глубине:
  quick  → sonar         ($0.006/запрос) — быстрые ответы
  medium → sonar-pro     ($0.02/запрос)  — развёрнутые ответы
  deep   → deep-research ($0.40/отчёт)  — полноценное исследование
"""

from __future__ import annotations

import time

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()

PERPLEXITY_BASE = "https://api.perplexity.ai"


async def research(
    query: str,
    depth: str = "auto",
    system_prompt: str = "",
) -> str | None:
    """Search with Perplexity Sonar API.

    Args:
        query: Search query.
        depth: "quick" | "medium" | "deep" | "auto".
        system_prompt: Optional system prompt for context.

    Returns:
        Research result text or None.
    """
    if not settings.perplexity_api_key:
        logger.warning("perplexity_not_configured")
        return None

    if depth == "auto":
        depth = _detect_depth(query)

    model = {
        "quick": "sonar",
        "medium": "sonar-pro",
        "deep": "sonar-deep-research",
    }.get(depth, "sonar")

    start = time.monotonic()

    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})

        payload = {
            "model": model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{PERPLEXITY_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.perplexity_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations", [])

        logger.info(
            "research_complete",
            model=model,
            depth=depth,
            elapsed_sec=round(elapsed, 2),
            citations=len(citations),
        )

        # Append citations if available
        if citations:
            text += "\n\n📎 Источники:\n"
            for i, url in enumerate(citations[:5], 1):
                text += f"{i}. {url}\n"

        return text

    except Exception as e:
        logger.error("research_error", model=model, error=str(e))
        return None


def _detect_depth(query: str) -> str:
    """Auto-detect research depth from query."""
    lower = query.lower()
    word_count = len(query.split())

    # Deep research indicators
    deep_words = ["исследуй", "анализ", "сравни", "обзор рынка", "подробно", "отчёт"]
    if any(w in lower for w in deep_words) or word_count > 30:
        return "deep"

    # Quick answer indicators
    quick_words = ["что такое", "кто такой", "какой курс", "погода", "сколько"]
    if any(w in lower for w in quick_words) or word_count <= 8:
        return "quick"

    return "medium"


async def quick_search(query: str) -> str | None:
    """Quick search (sonar) — for fast factual answers."""
    return await research(query, depth="quick")


async def deep_research(query: str) -> str | None:
    """Deep research — for comprehensive analysis."""
    return await research(
        query,
        depth="deep",
        system_prompt=(
            "Ты проводишь исследование для предпринимателя в сфере грузоперевозок "
            "(Санкт-Петербург). Ответь подробно, со структурой и выводами."
        ),
    )
