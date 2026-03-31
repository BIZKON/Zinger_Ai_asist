"""Handler: команды для работы с 1С.

Команды:
  /waybills — список последних накладных
  /waybill <номер> — статус конкретной накладной
  /orders — список заказов
"""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.services.one_c import (
    one_c,
    format_waybill,
    format_waybills_list,
    format_order,
)

logger = structlog.get_logger()

router = Router()


def _check_1c() -> str | None:
    """Return error message if 1С is not configured."""
    if not one_c.is_configured:
        return "1С не подключена. Настрой ONE_C_BASE_URL в .env"
    return None


@router.message(Command("waybills"))
async def cmd_waybills(message: Message) -> None:
    """Показать последние накладные."""
    err = _check_1c()
    if err:
        await message.answer(err)
        return

    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        waybills = await one_c.get_waybills(redis_client=redis_client)

        if not waybills:
            await message.answer("Накладных не найдено или 1С недоступна.")
            return

        text = "<b>📄 Последние накладные:</b>\n\n" + format_waybills_list(waybills)

        # Inline buttons for details
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📄 {wb.get('Number', '?')}",
                callback_data=f"wb:{wb.get('Number', '')}",
            )]
            for wb in waybills[:5]
            if wb.get("Number")
        ])

        await message.answer(text, reply_markup=keyboard if keyboard.inline_keyboard else None)

    except Exception as e:
        logger.error("waybills_error", error=str(e))
        await message.answer("Ошибка при получении накладных.")


@router.message(Command("waybill"))
async def cmd_waybill(message: Message) -> None:
    """Статус накладной: /waybill А-2847."""
    text = message.text or ""
    number = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not number:
        await message.answer("Укажи номер: /waybill А-2847")
        return

    err = _check_1c()
    if err:
        await message.answer(err)
        return

    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        wb = await one_c.get_waybill_by_number(number, redis_client=redis_client)

        if wb:
            await message.answer(format_waybill(wb))
        else:
            await message.answer(f"Накладная «{number}» не найдена.")

    except Exception as e:
        logger.error("waybill_error", error=str(e))
        await message.answer("Ошибка при запросе к 1С.")


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    """Показать последние заказы."""
    err = _check_1c()
    if err:
        await message.answer(err)
        return

    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        orders = await one_c.get_orders(redis_client=redis_client)

        if not orders:
            await message.answer("Заказов не найдено или 1С недоступна.")
            return

        lines = ["<b>📦 Последние заказы:</b>\n"]
        for o in orders[:10]:
            lines.append(format_order(o))
            lines.append("")

        await message.answer("\n".join(lines))

    except Exception as e:
        logger.error("orders_error", error=str(e))
        await message.answer("Ошибка при получении заказов.")
