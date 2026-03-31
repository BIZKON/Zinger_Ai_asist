"""Rate limiting middleware для aiogram.

Ограничивает количество сообщений на пользователя в минуту.
Использует Redis INCR + EXPIRE.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import redis.asyncio as aioredis
import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import settings

logger = structlog.get_logger()

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiter per user: N messages per minute."""

    def __init__(self, limit: int | None = None):
        self.limit = limit or settings.rate_limit_per_minute

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        # Admin bypass
        if user_id in settings.admin_ids:
            return await handler(event, data)

        try:
            client = await _get_redis()
            key = f"rl:{user_id}:{_current_minute()}"

            count = await client.incr(key)
            if count == 1:
                await client.expire(key, 60)

            if count > self.limit:
                logger.warning(
                    "rate_limited",
                    telegram_id=user_id,
                    count=count,
                    limit=self.limit,
                )
                await event.answer(
                    f"Слишком много сообщений. Лимит: {self.limit}/мин. "
                    "Подожди немного."
                )
                return None

        except Exception as e:
            # If Redis is down, don't block the user
            logger.warning("rate_limit_redis_error", error=str(e))

        return await handler(event, data)


def _current_minute() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
