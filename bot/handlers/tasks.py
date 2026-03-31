"""Handler: задачи CRUD.

Команды:
  /tasks — список активных задач
  /task <текст> — создать задачу
  /done <номер> — отметить задачу выполненной
"""

from __future__ import annotations

import asyncpg
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings

logger = structlog.get_logger()

router = Router()


async def _get_user_id(conn: asyncpg.Connection, telegram_id: int) -> str | None:
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE telegram_id = $1", telegram_id
    )
    return str(row["id"]) if row else None


@router.message(Command("tasks"))
async def cmd_tasks(message: Message) -> None:
    """Показать активные задачи."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала пройди /start.")
            return

        tasks = await conn.fetch(
            "SELECT id, title, priority, due_date, source FROM tasks "
            "WHERE user_id = $1::uuid AND status = 'active' "
            "ORDER BY "
            "  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "  WHEN 'medium' THEN 2 ELSE 3 END, "
            "  due_date ASC NULLS LAST "
            "LIMIT 20",
            user_id,
        )

        if not tasks:
            await message.answer("Активных задач нет. Свободен как ветер. 🌬")
            return

        lines = ["<b>📋 Активные задачи:</b>\n"]
        for i, t in enumerate(tasks, 1):
            emoji = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                t["priority"], "⚪"
            )
            due = f" (до {t['due_date'].strftime('%d.%m')})" if t["due_date"] else ""
            src = f" [{t['source']}]" if t["source"] != "chat" else ""
            lines.append(f"{i}. {emoji} {t['title']}{due}{src}")

        # Add inline buttons for completing
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ {i}",
                callback_data=f"task_done:{t['id']}",
            )]
            for i, t in enumerate(tasks[:5], 1)
        ])

        await message.answer("\n".join(lines), reply_markup=keyboard)

    except Exception as e:
        logger.error("tasks_error", error=str(e))
        await message.answer("Ошибка при получении задач.")
    finally:
        await conn.close()


@router.message(Command("task"))
async def cmd_create_task(message: Message) -> None:
    """Создать задачу: /task Позвонить Иванову по накладной."""
    text = message.text or ""
    # Remove the command part
    task_text = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not task_text:
        await message.answer("Напиши задачу после команды: /task Позвонить Иванову")
        return

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала пройди /start.")
            return

        # Detect priority from keywords
        priority = _detect_priority(task_text)

        await conn.execute(
            "INSERT INTO tasks (user_id, title, priority, source) "
            "VALUES ($1::uuid, $2, $3, 'chat')",
            user_id, task_text, priority,
        )

        emoji = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[priority]
        await message.answer(f"{emoji} Задача создана: <b>{task_text}</b>")

    except Exception as e:
        logger.error("task_create_error", error=str(e))
        await message.answer("Ошибка при создании задачи.")
    finally:
        await conn.close()


@router.message(Command("done"))
async def cmd_done(message: Message) -> None:
    """Отметить задачу выполненной: /done 1."""
    text = message.text or ""
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Укажи номер задачи: /done 1")
        return

    idx = int(parts[1]) - 1

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала пройди /start.")
            return

        tasks = await conn.fetch(
            "SELECT id, title FROM tasks "
            "WHERE user_id = $1::uuid AND status = 'active' "
            "ORDER BY "
            "  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "  WHEN 'medium' THEN 2 ELSE 3 END, "
            "  due_date ASC NULLS LAST "
            "LIMIT 20",
            user_id,
        )

        if idx < 0 or idx >= len(tasks):
            await message.answer("Нет такого номера задачи.")
            return

        task = tasks[idx]
        await conn.execute(
            "UPDATE tasks SET status = 'done', updated_at = NOW() "
            "WHERE id = $1",
            task["id"],
        )

        await message.answer(f"✅ Выполнено: <b>{task['title']}</b>")

    except Exception as e:
        logger.error("task_done_error", error=str(e))
        await message.answer("Ошибка при обновлении задачи.")
    finally:
        await conn.close()


def _detect_priority(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("срочно", "критично", "asap", "немедленно")):
        return "urgent"
    if any(w in lower for w in ("важно", "приоритет")):
        return "high"
    if any(w in lower for w in ("когда-нибудь", "потом", "не срочно")):
        return "low"
    return "medium"
