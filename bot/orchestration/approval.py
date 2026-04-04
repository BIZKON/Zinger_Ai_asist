"""Approval workflow: request human approval via Telegram inline buttons."""

from __future__ import annotations

from uuid import UUID

import asyncpg
import structlog
from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.orchestration import task_manager

logger = structlog.get_logger()


def _approval_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"agent_approve:{task_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"agent_reject:{task_id}"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"agent_info:{task_id}"),
        ],
    ])


async def request_approval(
    bot: Bot,
    user_telegram_id: int,
    task_id: UUID,
    description: str,
) -> None:
    """Send an approval request to the user via Telegram."""
    text = (
        "🤖 <b>Агент запрашивает одобрение</b>\n\n"
        f"{description}\n\n"
        "Подтвердите или отклоните действие:"
    )
    await bot.send_message(
        chat_id=user_telegram_id,
        text=text,
        reply_markup=_approval_keyboard(str(task_id)),
    )
    logger.info("approval_requested", task_id=str(task_id))


async def handle_approval_callback(
    callback: CallbackQuery,
    conn: asyncpg.Connection,
    task_id: str,
    decision: str,
) -> None:
    """Process the user's approval/rejection decision."""
    task = await task_manager.get_task(conn, UUID(task_id))
    if not task:
        await callback.answer("Задача не найдена.")
        return

    if task["status"] != "waiting_approval":
        await callback.answer("Задача уже обработана.")
        return

    if decision == "approve":
        await task_manager.update_status(conn, UUID(task_id), "pending")
        await callback.answer("✅ Одобрено — задача будет выполнена.")
        if callback.message:
            await callback.message.edit_text(
                f"✅ <b>Одобрено:</b> {task['title']}",
            )

    elif decision == "reject":
        await task_manager.update_status(
            conn, UUID(task_id), "cancelled",
            result={"reason": "rejected_by_user"},
        )
        await callback.answer("❌ Отклонено.")
        if callback.message:
            await callback.message.edit_text(
                f"❌ <b>Отклонено:</b> {task['title']}",
            )

    elif decision == "info":
        info = (
            f"📋 <b>{task['title']}</b>\n"
            f"Статус: {task['status']}\n"
            f"Приоритет: {task['priority']}\n"
        )
        if task.get("description"):
            info += f"Описание: {task['description']}\n"
        await callback.answer()
        if callback.message:
            await callback.message.answer(info)
