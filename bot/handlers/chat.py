"""Handler: текстовые сообщения → persona + memory + LLM."""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
import structlog
from aiogram import Router
from aiogram.types import Message

from bot.config import settings
from bot.services import llm, memory
from bot.services.persona import build_system_prompt, detect_mood

logger = structlog.get_logger()

router = Router()

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def _get_or_create_user(conn: asyncpg.Connection, tg_user) -> dict | None:
    """Get user from DB or create if first message."""
    row = await conn.fetchrow(
        "SELECT id, name, persona, timezone FROM users WHERE telegram_id = $1",
        tg_user.id,
    )
    if row:
        return dict(row)

    # Auto-create user on first message
    row = await conn.fetchrow(
        "INSERT INTO users (telegram_id, name) VALUES ($1, $2) RETURNING id, name, persona, timezone",
        tg_user.id,
        tg_user.first_name,
    )
    logger.info("user_auto_created", telegram_id=tg_user.id)
    return dict(row)


@router.message()
async def handle_text(message: Message) -> None:
    """Handle all text messages — main conversational loop."""
    if not message.text:
        return

    user_text = message.text.strip()
    if not user_text:
        return

    # Skip commands (handled by other routers)
    if user_text.startswith("/"):
        return

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(settings.database_url_raw)
        redis_client = await _get_redis()

        # Get or create user
        user = await _get_or_create_user(conn, message.from_user)
        if not user:
            await message.answer("Произошла ошибка. Попробуй /start")
            return

        user_id = str(user["id"])
        persona_key = user.get("persona") or settings.default_persona
        user_name = user.get("name") or message.from_user.first_name

        # Detect mood
        mood = detect_mood(user_text)

        # Build context from memory
        facts_text, history = await memory.build_context(
            conn, redis_client, user_id, user_text,
        )

        # Add current time to context
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        context = f"Текущее время: {now}"

        # Build system prompt
        system_prompt = build_system_prompt(
            persona_key=persona_key,
            mood=mood,
            user_name=user_name,
            user_facts=facts_text,
            context=context,
        )

        # Prepare messages for LLM
        messages = history.copy()
        messages.append({"role": "user", "content": user_text})

        # Call LLM
        reply = await llm.chat(
            messages=messages,
            system_prompt=system_prompt,
        )

        # Send response
        await message.answer(reply)

        # Save to working memory
        await memory.append_working_memory(redis_client, user_id, "user", user_text)
        await memory.append_working_memory(redis_client, user_id, "assistant", reply)

        # Extract facts in background (don't block response)
        dialog = f"Пользователь: {user_text}\nАссистент: {reply}"
        await memory.extract_and_save_facts(conn, user_id, dialog)

    except Exception as e:
        logger.error("chat_handler_error", error=str(e))
        await message.answer("Что-то пошло не так. Попробуй ещё раз.")

    finally:
        if conn:
            await conn.close()
