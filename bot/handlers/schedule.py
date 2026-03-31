"""Handler: расписание, события, поиск.

Команды:
  /search <запрос> — поиск через Perplexity
  /research <тема> — глубокое исследование
  /events — события на сегодня/завтра
  /remind <текст> — создать напоминание
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.services.persona import build_system_prompt
from bot.services import llm

logger = structlog.get_logger()

router = Router()


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    """Быстрый поиск через Perplexity."""
    text = message.text or ""
    query = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not query:
        await message.answer("Что искать? /search тарифы грузоперевозок СПб")
        return

    await message.answer("🔍 Ищу...")

    from bot.services.research import research

    result = await research(query, depth="quick")

    if result:
        # Format through persona
        conn = await asyncpg.connect(settings.database_url_raw)
        try:
            user = await conn.fetchrow(
                "SELECT persona, name FROM users WHERE telegram_id = $1",
                message.from_user.id,
            )
            persona = user["persona"] if user else "sergiy"
            user_name = user["name"] if user else message.from_user.first_name

            system = build_system_prompt(
                persona_key=persona,
                user_name=user_name,
                context=f"Пользователь спросил: {query}",
            )

            formatted = await llm.chat(
                messages=[{"role": "user", "content": f"Перескажи кратко в своём стиле:\n\n{result[:2000]}"}],
                system_prompt=system,
                complexity="medium",
            )
            await message.answer(formatted[:4000])

        except Exception as e:
            logger.warning("search_format_error", error=str(e))
            await message.answer(result[:4000])
        finally:
            await conn.close()
    else:
        await message.answer("Не удалось найти информацию. Perplexity API не настроен или недоступен.")


@router.message(Command("research"))
async def cmd_research(message: Message) -> None:
    """Глубокое исследование через Perplexity."""
    text = message.text or ""
    query = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not query:
        await message.answer("Что исследовать? /research анализ конкурентов грузоперевозки")
        return

    await message.answer("📊 Запускаю исследование... Это может занять 1-2 минуты.")

    from bot.services.research import deep_research

    result = await deep_research(query)

    if result:
        # Split long results
        if len(result) > 4000:
            parts = [result[i:i+4000] for i in range(0, len(result), 4000)]
            for part in parts[:3]:  # Max 3 messages
                await message.answer(part)
        else:
            await message.answer(result)
    else:
        await message.answer("Не удалось провести исследование.")


@router.message(Command("events"))
async def cmd_events(message: Message) -> None:
    """Показать события на сегодня/завтра."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            message.from_user.id,
        )
        if not user:
            await message.answer("Сначала пройди /start.")
            return

        user_id = str(user["id"])

        # Get tasks with due dates for today/tomorrow
        now = datetime.now(timezone.utc)
        tomorrow = now + __import__("datetime").timedelta(days=1)

        tasks = await conn.fetch(
            "SELECT title, priority, due_date FROM tasks "
            "WHERE user_id = $1::uuid AND status = 'active' "
            "AND due_date IS NOT NULL AND due_date <= $2 "
            "ORDER BY due_date ASC",
            user_id, tomorrow,
        )

        # Get scheduled facts (meetings, events)
        events = await conn.fetch(
            "SELECT key, value FROM memory_structured "
            "WHERE user_id = $1::uuid AND category = 'work' "
            "AND key ILIKE '%встреча%' AND is_active = TRUE",
            user_id,
        )

        lines = ["<b>📅 События:</b>\n"]

        if tasks:
            lines.append("<b>Задачи с дедлайном:</b>")
            for t in tasks:
                emoji = {"urgent": "🔴", "high": "🟠", "medium": "🟡"}.get(t["priority"], "⚪")
                due = t["due_date"].strftime("%d.%m %H:%M") if t["due_date"] else ""
                lines.append(f"  {emoji} {t['title']} — {due}")

        if events:
            lines.append("\n<b>Встречи:</b>")
            for e in events:
                lines.append(f"  📌 {e['key']}: {e['value']}")

        if len(lines) == 1:
            lines.append("Нет запланированных событий. Свободный день!")

        await message.answer("\n".join(lines))

    except Exception as e:
        logger.error("events_error", error=str(e))
        await message.answer("Ошибка при получении событий.")
    finally:
        await conn.close()


@router.message(Command("remind"))
async def cmd_remind(message: Message) -> None:
    """Создать напоминание: /remind завтра 15:00 позвонить в банк."""
    text = message.text or ""
    reminder_text = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not reminder_text:
        await message.answer(
            "Формат: /remind <текст напоминания>\n"
            "Пример: /remind Позвонить в банк завтра"
        )
        return

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            message.from_user.id,
        )
        if not user:
            await message.answer("Сначала пройди /start.")
            return

        # Save as task with source='reminder'
        await conn.execute(
            "INSERT INTO tasks (user_id, title, priority, source) "
            "VALUES ($1, $2, 'medium', 'reminder')",
            user["id"], reminder_text,
        )

        await message.answer(f"⏰ Напоминание создано: <b>{reminder_text}</b>")

    except Exception as e:
        logger.error("remind_error", error=str(e))
        await message.answer("Ошибка при создании напоминания.")
    finally:
        await conn.close()
