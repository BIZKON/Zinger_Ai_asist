"""Handler: управление звонками из Telegram.

Команды:
  /call <имя или телефон> — инициировать звонок
  /calls — история звонков
"""

from __future__ import annotations

import asyncpg
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings

logger = structlog.get_logger()

router = Router()


async def _get_user(conn: asyncpg.Connection, telegram_id: int) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id, name, persona, voice_id FROM users WHERE telegram_id = $1",
        telegram_id,
    )
    return dict(row) if row else None


@router.message(Command("call"))
async def cmd_call(message: Message) -> None:
    """Инициировать звонок: /call Иванов или /call +79111234567."""
    text = message.text or ""
    target = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not target:
        await message.answer(
            "Укажи кому звонить:\n"
            "/call Иванов\n"
            "/call +79111234567"
        )
        return

    if not settings.voximplant_account_id:
        await message.answer(
            "Телефония не настроена. "
            "Настрой VOXIMPLANT_ACCOUNT_ID в .env"
        )
        return

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user = await _get_user(conn, message.from_user.id)
        if not user:
            await message.answer("Сначала пройди /start.")
            return

        # Determine if target is phone or name
        is_phone = target.startswith("+") or target.replace("-", "").isdigit()

        if is_phone:
            phone = target
            contact_name = ""
        else:
            # Search in contacts/1С
            contact_name = target
            phone = ""

            # Try to find phone in contacts table
            row = await conn.fetchrow(
                "SELECT phone FROM contacts WHERE user_id = $1::uuid "
                "AND name ILIKE $2 LIMIT 1",
                str(user["id"]), f"%{target}%",
            )
            if row and row["phone"]:
                phone = row["phone"]

        if not phone:
            await message.answer(
                f"Не нашёл номер для «{target}». "
                f"Укажи номер напрямую: /call +79111234567"
            )
            return

        # Confirmation keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Позвонить",
                    callback_data=f"call_start:{phone}:{contact_name}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="call_cancel",
                ),
            ]
        ])

        display = f"{contact_name} ({phone})" if contact_name else phone
        await message.answer(
            f"Звоню <b>{display}</b>?",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("call_cmd_error", error=str(e))
        await message.answer("Ошибка при подготовке звонка.")
    finally:
        await conn.close()


@router.message(Command("calls"))
async def cmd_calls_history(message: Message) -> None:
    """Показать историю звонков."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user = await _get_user(conn, message.from_user.id)
        if not user:
            await message.answer("Сначала пройди /start.")
            return

        sessions = await conn.fetch(
            "SELECT contact_name, contact_phone, direction, outcome, "
            "duration_sec, summary, created_at "
            "FROM call_sessions WHERE user_id = $1::uuid "
            "ORDER BY created_at DESC LIMIT 10",
            str(user["id"]),
        )

        if not sessions:
            await message.answer("Звонков пока не было.")
            return

        lines = ["<b>📞 История звонков:</b>\n"]
        for s in sessions:
            direction = "📤" if s["direction"] == "outbound" else "📥"
            name = s["contact_name"] or s["contact_phone"] or "?"
            outcome_emoji = {
                "confirmed": "✅",
                "declined": "❌",
                "callback": "🔄",
                "no_answer": "📵",
                "completed": "✅",
            }.get(s["outcome"] or "", "⚪")

            dur = f"{s['duration_sec']}с" if s["duration_sec"] else ""
            date = s["created_at"].strftime("%d.%m %H:%M") if s["created_at"] else ""

            lines.append(f"{direction} {outcome_emoji} <b>{name}</b> {dur} ({date})")

            if s["summary"]:
                # Show first 80 chars of summary
                summary = s["summary"][:80] + "..." if len(s["summary"] or "") > 80 else s["summary"]
                lines.append(f"   <i>{summary}</i>")

        await message.answer("\n".join(lines))

    except Exception as e:
        logger.error("calls_history_error", error=str(e))
        await message.answer("Ошибка при получении истории звонков.")
    finally:
        await conn.close()
