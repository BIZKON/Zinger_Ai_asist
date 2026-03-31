"""Handler: подписки и оплата.

Команды:
  /subscribe — выбрать тариф
  /billing — информация о подписке
"""

from __future__ import annotations

import asyncpg
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.services.payment import (
    TIERS,
    create_payment,
    format_all_tiers,
    format_tier_info,
)

logger = structlog.get_logger()

router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    """Показать тарифы и выбрать подписку."""
    text = format_all_tiers()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💎 {info['name']} — {info['price']} ₽",
            callback_data=f"pay:{key}",
        )]
        for key, info in TIERS.items()
    ])

    await message.answer(text, reply_markup=keyboard)


@router.message(Command("billing"))
async def cmd_billing(message: Message) -> None:
    """Показать информацию о текущей подписке."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user = await conn.fetchrow(
            "SELECT tier FROM users WHERE telegram_id = $1",
            message.from_user.id,
        )
        if not user:
            await message.answer("Сначала пройди /start.")
            return

        tier = user["tier"] or "free"
        lines = [f"<b>Текущий тариф:</b> {tier.upper()}\n"]

        # Last payment
        payment = await conn.fetchrow(
            "SELECT amount, status, created_at FROM payments "
            "WHERE user_id = (SELECT id FROM users WHERE telegram_id = $1) "
            "ORDER BY created_at DESC LIMIT 1",
            message.from_user.id,
        )

        if payment:
            date = payment["created_at"].strftime("%d.%m.%Y") if payment["created_at"] else ""
            lines.append(f"Последний платёж: {payment['amount']} ₽ ({payment['status']}) {date}")

        lines.append("\n/subscribe — изменить тариф")
        await message.answer("\n".join(lines))

    except Exception as e:
        logger.error("billing_error", error=str(e))
        await message.answer("Ошибка при получении информации о подписке.")
    finally:
        await conn.close()


@router.callback_query(lambda c: c.data and c.data.startswith("pay:"))
async def callback_pay(callback: CallbackQuery) -> None:
    """Обработать выбор тарифа — создать платёж."""
    tier = callback.data.split(":", 1)[1]

    if tier not in TIERS:
        await callback.answer("Неизвестный тариф.")
        return

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            callback.from_user.id,
        )
        if not user:
            await callback.answer("Пройди /start сначала.")
            return

        user_id = str(user["id"])

        result = await create_payment(
            user_id=user_id,
            tier=tier,
            telegram_id=callback.from_user.id,
        )

        if result and result.get("confirmation_url"):
            # Save pending payment
            await conn.execute(
                "INSERT INTO payments (user_id, yukassa_payment_id, amount, tier, status) "
                "VALUES ($1::uuid, $2, $3, $4, 'pending')",
                user_id, result["payment_id"], result["amount"], tier,
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💳 Оплатить",
                    url=result["confirmation_url"],
                )]
            ])

            await callback.message.answer(
                f"Оплата тарифа <b>{TIERS[tier]['name']}</b>: {TIERS[tier]['price']} ₽",
                reply_markup=keyboard,
            )
        else:
            await callback.message.answer(
                "ЮKassa не настроена. Обратись к администратору."
            )

        await callback.answer()

    except Exception as e:
        logger.error("payment_callback_error", error=str(e))
        await callback.answer("Ошибка при создании платежа.")
    finally:
        await conn.close()
