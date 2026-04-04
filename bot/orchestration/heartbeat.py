"""Heartbeat Engine: APScheduler-based periodic agent wake-ups."""

from __future__ import annotations

import json

import asyncpg
import structlog
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings
from bot.orchestration.router import execute_agent_tick

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None
_bot_ref: Bot | None = None


async def start(bot: Bot) -> None:
    """Start the heartbeat scheduler and load agent cron jobs."""
    global _scheduler, _bot_ref

    if not settings.agent_heartbeat_enabled:
        logger.info("heartbeat_disabled")
        return

    _bot_ref = bot
    _scheduler = AsyncIOScheduler()

    # Load all active agents and register their cron jobs
    try:
        conn = await asyncpg.connect(settings.database_url_raw)
        try:
            agents = await conn.fetch(
                "SELECT id, slug, heartbeat_cron FROM agent_configs WHERE is_active = TRUE",
            )
            for agent in agents:
                _add_agent_job(str(agent["id"]), agent["slug"], agent["heartbeat_cron"])
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("heartbeat_no_agents", error=str(e))

    _scheduler.start()
    logger.info("heartbeat_started", agents=len(agents) if 'agents' in dir() else 0)


async def stop() -> None:
    """Gracefully stop the scheduler."""
    global _scheduler, _bot_ref
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        _bot_ref = None
        logger.info("heartbeat_stopped")


def _add_agent_job(agent_id: str, slug: str, cron_expr: str) -> None:
    """Add a cron job for a single agent."""
    if not _scheduler:
        return

    try:
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.error("invalid_cron", slug=slug, cron=cron_expr)
            return

        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4],
        )
        _scheduler.add_job(
            _tick,
            trigger=trigger,
            args=[agent_id],
            id=f"heartbeat_{slug}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.debug("agent_job_added", slug=slug, cron=cron_expr)
    except Exception as e:
        logger.error("agent_job_error", slug=slug, error=str(e))


async def _tick(agent_config_id: str) -> None:
    """Execute a single agent heartbeat cycle."""
    if not _bot_ref:
        return

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        result = await execute_agent_tick(agent_config_id, _bot_ref, conn)
        logger.info("heartbeat_tick", agent=agent_config_id, **result)
    except Exception as e:
        logger.error("heartbeat_tick_error", agent=agent_config_id, error=str(e))
    finally:
        await conn.close()


def reload_agent(agent_id: str, slug: str, cron_expr: str) -> None:
    """Reload a single agent's cron schedule (e.g. after config change)."""
    if _scheduler:
        job_id = f"heartbeat_{slug}"
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
        _add_agent_job(agent_id, slug, cron_expr)
