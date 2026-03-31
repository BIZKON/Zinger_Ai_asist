"""6-слойная память (pgvector).

Слои:
  1. Structured — факты (семья, авто, еда, здоровье)
  2. Semantic — векторный поиск по диалогам
  3. Episodic — саммари разговоров
  4. Procedural — привычки и паттерны
  5. Working — текущий контекст сессии
  6. Meta — настройки и предпочтения
"""

from __future__ import annotations

import json
from datetime import date

import asyncpg
import structlog

from bot.config import settings
from bot.services import llm

logger = structlog.get_logger()


# ── Layer 1: Structured Memory (facts) ──

async def get_user_facts(conn: asyncpg.Connection, user_id: str) -> list[dict]:
    """Get all active structured facts for a user."""
    rows = await conn.fetch(
        "SELECT category, key, value FROM memory_structured "
        "WHERE user_id = $1 AND is_active = TRUE "
        "ORDER BY category, key",
        user_id,
    )
    return [dict(r) for r in rows]


async def get_user_facts_text(conn: asyncpg.Connection, user_id: str) -> str:
    """Get user facts formatted as text for system prompt."""
    facts = await get_user_facts(conn, user_id)
    if not facts:
        return ""

    lines = []
    current_cat = None
    for f in facts:
        if f["category"] != current_cat:
            current_cat = f["category"]
            lines.append(f"\n[{current_cat}]")
        lines.append(f"  {f['key']}: {f['value']}")

    return "\n".join(lines)


async def save_fact(
    conn: asyncpg.Connection,
    user_id: str,
    category: str,
    key: str,
    value: str,
) -> None:
    """Save or update a structured fact."""
    await conn.execute(
        """
        INSERT INTO memory_structured (user_id, category, key, value, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT ON CONSTRAINT memory_structured_user_cat_key
            DO UPDATE SET value = $4, updated_at = NOW(), is_active = TRUE
        """,
        user_id, category, key, value,
    )
    logger.debug("fact_saved", user_id=user_id, category=category, key=key)


async def extract_and_save_facts(
    conn: asyncpg.Connection,
    user_id: str,
    dialog_text: str,
) -> None:
    """Use LLM to extract facts from dialog and save them.

    Asks Claude to find structured facts in the conversation
    and returns them as JSON.
    """
    prompt = (
        "Извлеки факты о пользователе из этого диалога.\n"
        "Верни JSON массив объектов с полями: category, key, value.\n"
        "Категории: family, auto, food, sport, health, work, preferences, other.\n"
        "Если фактов нет — верни пустой массив [].\n"
        "Только JSON, без markdown.\n\n"
        f"Диалог:\n{dialog_text}"
    )

    try:
        response = await llm.extract_json(prompt)
        facts = json.loads(response)

        if not isinstance(facts, list):
            return

        for fact in facts:
            if all(k in fact for k in ("category", "key", "value")):
                await save_fact(
                    conn, user_id,
                    fact["category"], fact["key"], str(fact["value"]),
                )

    except (json.JSONDecodeError, Exception) as e:
        logger.warning("fact_extraction_failed", error=str(e))


# ── Layer 3: Episodic Memory (conversation summaries) ──

async def save_episode(
    conn: asyncpg.Connection,
    user_id: str,
    summary: str,
    session_date: date | None = None,
) -> None:
    """Save a conversation summary (episodic memory)."""
    if session_date is None:
        session_date = date.today()

    await conn.execute(
        "INSERT INTO memory_episodic (user_id, summary, session_date) "
        "VALUES ($1, $2, $3)",
        user_id, summary, session_date,
    )
    logger.debug("episode_saved", user_id=user_id)


async def get_recent_episodes(
    conn: asyncpg.Connection,
    user_id: str,
    limit: int = 5,
) -> list[dict]:
    """Get recent conversation summaries."""
    rows = await conn.fetch(
        "SELECT summary, session_date FROM memory_episodic "
        "WHERE user_id = $1 "
        "ORDER BY created_at DESC LIMIT $2",
        user_id, limit,
    )
    return [dict(r) for r in rows]


# ── Layer 5: Working Memory (session context) ──

# Working memory is stored in Redis for the current session.
# Format: session:{user_id} → list of recent messages (JSON).

async def get_working_memory(redis_client, user_id: str, limit: int = 20) -> list[dict]:
    """Get recent messages from working memory (Redis)."""
    key = f"session:{user_id}"
    try:
        raw = await redis_client.lrange(key, 0, limit - 1)
        return [json.loads(m) for m in raw]
    except Exception:
        return []


async def append_working_memory(
    redis_client,
    user_id: str,
    role: str,
    content: str,
    ttl: int = 3600 * 4,  # 4 hours
) -> None:
    """Append a message to working memory."""
    key = f"session:{user_id}"
    msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
    try:
        await redis_client.lpush(key, msg)
        await redis_client.ltrim(key, 0, 29)  # Keep last 30 messages
        await redis_client.expire(key, ttl)
    except Exception as e:
        logger.warning("working_memory_error", error=str(e))


# ── Context Assembly ──

async def build_context(
    conn: asyncpg.Connection,
    redis_client,
    user_id: str,
    current_message: str,
) -> tuple[str, list[dict]]:
    """Assemble full context for LLM call.

    Returns:
        (user_facts_text, conversation_history)
    """
    # Layer 1: Structured facts
    facts_text = await get_user_facts_text(conn, user_id)

    # Layer 3: Recent episodes (for context)
    episodes = await get_recent_episodes(conn, user_id, limit=3)
    if episodes:
        ep_lines = [f"- [{e['session_date']}] {e['summary']}" for e in episodes]
        if facts_text:
            facts_text += "\n\n[Недавние разговоры]\n" + "\n".join(ep_lines)
        else:
            facts_text = "[Недавние разговоры]\n" + "\n".join(ep_lines)

    # Layer 5: Working memory (conversation history)
    history = await get_working_memory(redis_client, user_id)
    # Reverse because lpush adds to the beginning
    history.reverse()

    return facts_text, history
