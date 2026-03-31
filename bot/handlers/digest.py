"""Handler: утренний/вечерний дайджест.

Cron 08:00 по timezone пользователя:
  - Погода + пробки
  - 3 горящие задачи
  - События дня
  - Проактивный вопрос в характере Сергия
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
import structlog
from aiogram import Bot, Router
from aiogram.types import Message
from aiogram.filters import Command

from bot.config import settings
from bot.services import llm
from bot.services.persona import build_system_prompt
from bot.services.weather import get_weather, format_weather
from bot.services.traffic import get_traffic, format_traffic

logger = structlog.get_logger()

router = Router()


async def _build_digest(
    user_id: str,
    user_name: str,
    persona_key: str,
    city: str,
    redis_client: aioredis.Redis | None = None,
    conn: asyncpg.Connection | None = None,
) -> str:
    """Build morning digest content."""
    parts: list[str] = []

    # Weather
    weather = await get_weather(city=city, redis_client=redis_client)
    if weather:
        parts.append(f"<b>Погода в {city}:</b>\n{format_weather(weather)}")

    # Traffic
    traffic = await get_traffic(redis_client=redis_client)
    if traffic:
        parts.append(f"\n<b>Дорога:</b>\n{format_traffic(traffic)}")

    # Top tasks
    if conn:
        try:
            tasks = await conn.fetch(
                "SELECT title, priority, due_date FROM tasks "
                "WHERE user_id = $1::uuid AND status = 'active' "
                "ORDER BY "
                "  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
                "  WHEN 'medium' THEN 2 ELSE 3 END, "
                "  due_date ASC NULLS LAST "
                "LIMIT 3",
                user_id,
            )
            if tasks:
                task_lines = []
                for t in tasks:
                    priority_emoji = {
                        "urgent": "🔴", "high": "🟠",
                        "medium": "🟡", "low": "🟢",
                    }.get(t["priority"], "⚪")
                    due = f" (до {t['due_date'].strftime('%d.%m')})" if t["due_date"] else ""
                    task_lines.append(f"  {priority_emoji} {t['title']}{due}")
                parts.append("\n<b>Задачи:</b>\n" + "\n".join(task_lines))
        except Exception as e:
            logger.warning("digest_tasks_error", error=str(e))

    raw_data = "\n".join(parts) if parts else "Нет данных для дайджеста."

    # Let LLM format it in persona style
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    system = build_system_prompt(
        persona_key=persona_key,
        mood="neutral",
        user_name=user_name,
        context=f"Текущее время: {now}",
    )

    prompt = (
        f"Составь утренний дайджест на основе этих данных. "
        f"Будь краток, добавь характерный комментарий в своём стиле.\n\n"
        f"{raw_data}"
    )

    reply = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=system,
        complexity="medium",
    )

    return reply


@router.message(Command("digest"))
async def cmd_digest(message: Message) -> None:
    """Manual digest command."""
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(settings.database_url_raw)
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

        user = await conn.fetchrow(
            "SELECT id, name, persona, city FROM users WHERE telegram_id = $1",
            message.from_user.id,
        )

        if not user:
            await message.answer("Сначала пройди /start, чтобы я тебя узнал.")
            return

        await message.answer("⏳ Собираю дайджест...")

        digest = await _build_digest(
            user_id=str(user["id"]),
            user_name=user["name"] or message.from_user.first_name,
            persona_key=user["persona"] or settings.default_persona,
            city=user["city"] or "Санкт-Петербург",
            redis_client=redis_client,
            conn=conn,
        )

        await message.answer(digest)

    except Exception as e:
        logger.error("digest_error", error=str(e))
        await message.answer("Не удалось собрать дайджест. Попробуй позже.")

    finally:
        if conn:
            await conn.close()


async def send_morning_digest(bot: Bot) -> None:
    """Send morning digest to all users. Called by scheduler.

    Should be triggered by APScheduler or similar cron at 08:00 per timezone.
    """
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(settings.database_url_raw)
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

        users = await conn.fetch(
            "SELECT id, telegram_id, name, persona, city FROM users"
        )

        for user in users:
            try:
                digest = await _build_digest(
                    user_id=str(user["id"]),
                    user_name=user["name"] or "друг",
                    persona_key=user["persona"] or settings.default_persona,
                    city=user["city"] or "Санкт-Петербург",
                    redis_client=redis_client,
                    conn=conn,
                )
                await bot.send_message(user["telegram_id"], digest)
                logger.info("digest_sent", telegram_id=user["telegram_id"])

            except Exception as e:
                logger.warning(
                    "digest_send_error",
                    telegram_id=user["telegram_id"],
                    error=str(e),
                )

    except Exception as e:
        logger.error("morning_digest_error", error=str(e))

    finally:
        if conn:
            await conn.close()
