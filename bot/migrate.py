"""Simple SQL migration runner.

Reads db/migrations/*.sql in sorted order, tracks applied migrations
in a _migrations table, and executes unapplied ones.

Usage: python -m bot.migrate
"""

import asyncio
import glob
import os

import asyncpg
import structlog

from bot.config import settings

logger = structlog.get_logger()

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "migrations")


async def run_migrations() -> None:
    conn = await asyncpg.connect(settings.database_url_raw)

    try:
        # Create migrations tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Get already applied migrations
        applied = {
            row["name"]
            for row in await conn.fetch("SELECT name FROM _migrations")
        }

        # Find and sort migration files
        pattern = os.path.join(MIGRATIONS_DIR, "*.sql")
        files = sorted(glob.glob(pattern))

        for filepath in files:
            name = os.path.basename(filepath)
            if name in applied:
                logger.debug("migration_skipped", name=name)
                continue

            sql = open(filepath).read().strip()
            if not sql or sql.startswith("-- TODO"):
                logger.debug("migration_empty", name=name)
                continue

            logger.info("migration_applying", name=name)
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO _migrations (name) VALUES ($1)", name
            )
            logger.info("migration_applied", name=name)

    finally:
        await conn.close()

    logger.info("migrations_complete")


if __name__ == "__main__":
    asyncio.run(run_migrations())
