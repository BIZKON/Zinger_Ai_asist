"""Handler: контакты и контрагенты из 1С.

Команды:
  /contacts — список контрагентов
  /contact <имя> — поиск контрагента
"""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.services.one_c import one_c, format_contractor

logger = structlog.get_logger()

router = Router()


@router.message(Command("contacts"))
async def cmd_contacts(message: Message) -> None:
    """Показать список контрагентов из 1С."""
    if not one_c.is_configured:
        await message.answer("1С не подключена. Настрой ONE_C_BASE_URL в .env")
        return

    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        contractors = await one_c.get_contractors(redis_client=redis_client)

        if not contractors:
            await message.answer("Контрагенты не найдены или 1С недоступна.")
            return

        lines = ["<b>📇 Контрагенты:</b>\n"]
        for c in contractors[:15]:
            lines.append(format_contractor(c))
            lines.append("")

        await message.answer("\n".join(lines))

    except Exception as e:
        logger.error("contacts_error", error=str(e))
        await message.answer("Ошибка при получении контрагентов.")


@router.message(Command("contact"))
async def cmd_search_contact(message: Message) -> None:
    """Поиск контрагента: /contact Иванов."""
    text = message.text or ""
    query = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

    if not query:
        await message.answer("Укажи имя для поиска: /contact Иванов")
        return

    if not one_c.is_configured:
        await message.answer("1С не подключена.")
        return

    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        results = await one_c.search_contractor(query, redis_client=redis_client)

        if not results:
            await message.answer(f"Контрагент «{query}» не найден в 1С.")
            return

        lines = [f"<b>🔍 Поиск: {query}</b>\n"]
        for c in results[:10]:
            lines.append(format_contractor(c))
            lines.append("")

        await message.answer("\n".join(lines))

    except Exception as e:
        logger.error("contact_search_error", error=str(e))
        await message.answer("Ошибка при поиске контрагента.")
