"""Handler: inline-кнопки и callback queries.

Обрабатывает callback_data:
  task_done:{task_id} — выполнить задачу
  wb:{number} — показать накладную
  order:{ref} — показать заказ
"""

from __future__ import annotations

import asyncpg
import redis.asyncio as aioredis
import structlog
from aiogram import Router
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.services.one_c import one_c, format_waybill

logger = structlog.get_logger()

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("task_done:"))
async def callback_task_done(callback: CallbackQuery) -> None:
    """Отметить задачу выполненной по inline-кнопке."""
    task_id = callback.data.split(":", 1)[1]

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        row = await conn.fetchrow(
            "UPDATE tasks SET status = 'done', updated_at = NOW() "
            "WHERE id = $1::uuid RETURNING title",
            task_id,
        )

        if row:
            await callback.answer(f"✅ {row['title']}")
            # Edit the message to reflect the change
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
        else:
            await callback.answer("Задача не найдена.")

    except Exception as e:
        logger.error("callback_task_done_error", error=str(e))
        await callback.answer("Ошибка.")
    finally:
        await conn.close()


@router.callback_query(lambda c: c.data and c.data.startswith("wb:"))
async def callback_waybill(callback: CallbackQuery) -> None:
    """Показать детали накладной."""
    number = callback.data.split(":", 1)[1]

    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        wb = await one_c.get_waybill_by_number(number, redis_client=redis_client)

        if wb:
            await callback.message.answer(format_waybill(wb))
        else:
            await callback.message.answer(f"Накладная {number} не найдена в 1С.")

        await callback.answer()

    except Exception as e:
        logger.error("callback_waybill_error", error=str(e))
        await callback.answer("Ошибка при запросе к 1С.")
