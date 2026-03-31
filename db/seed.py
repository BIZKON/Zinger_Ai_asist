"""Seed test data for development."""

import asyncio

import asyncpg
import structlog

from bot.config import settings

logger = structlog.get_logger()


async def seed() -> None:
    conn = await asyncpg.connect(settings.database_url_raw)

    try:
        # Test user
        await conn.execute("""
            INSERT INTO users (telegram_id, name, city, persona, tier)
            VALUES (123456789, 'Сергей Доронин', 'Санкт-Петербург', 'sergiy', 'pro')
            ON CONFLICT (telegram_id) DO NOTHING
        """)

        logger.info("seed_complete")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
