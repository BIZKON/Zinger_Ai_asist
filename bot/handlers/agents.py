"""Handler: agent orchestration commands.

Commands:
  /agents        — list user's agent configs
  /agent_status  — detailed status of one agent
  /goals         — list active goals
  /goal          — create a new goal
  /agent_cost    — LLM cost summary
"""

from __future__ import annotations

import json

import asyncpg
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.orchestration import cost_monitor, goal_tracker

logger = structlog.get_logger()

router = Router()


async def _get_user_id(conn: asyncpg.Connection, telegram_id: int):
    """Resolve internal user_id from telegram_id."""
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE telegram_id = $1", telegram_id,
    )
    return row["id"] if row else None


@router.message(Command("agents"))
async def cmd_agents(message: Message) -> None:
    """List active agents for the user."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала выполните /start для регистрации.")
            return

        agents = await conn.fetch(
            "SELECT slug, display_name, role, is_active, heartbeat_cron "
            "FROM agent_configs WHERE user_id = $1 ORDER BY created_at",
            user_id,
        )

        if not agents:
            await message.answer(
                "🤖 У вас нет агентов.\n"
                "Агенты создаются администратором через настройки.",
            )
            return

        lines = ["🤖 <b>Ваши агенты:</b>\n"]
        for a in agents:
            status = "🟢" if a["is_active"] else "🔴"
            lines.append(
                f"{status} <b>{a['display_name']}</b> ({a['slug']})\n"
                f"   Роль: {a['role']} | Расписание: {a['heartbeat_cron']}"
            )

        await message.answer("\n".join(lines))
    except Exception as e:
        logger.error("cmd_agents_error", error=str(e))
        await message.answer("Ошибка при загрузке агентов.")
    finally:
        await conn.close()


@router.message(Command("agent_status"))
async def cmd_agent_status(message: Message) -> None:
    """Show detailed status for an agent: /agent_status <slug>."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /agent_status <slug>")
        return

    slug = parts[1].strip()
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала выполните /start.")
            return

        agent = await conn.fetchrow(
            "SELECT * FROM agent_configs WHERE user_id = $1 AND slug = $2",
            user_id, slug,
        )
        if not agent:
            await message.answer(f"Агент «{slug}» не найден.")
            return

        # Recent heartbeats
        beats = await conn.fetch(
            "SELECT triggered_at, duration_ms, tasks_completed, error "
            "FROM heartbeat_log WHERE agent_id = $1 ORDER BY triggered_at DESC LIMIT 5",
            agent["id"],
        )

        # Active tasks count
        task_counts = await conn.fetchrow(
            "SELECT COUNT(*) FILTER (WHERE status = 'pending') AS pending, "
            "COUNT(*) FILTER (WHERE status = 'in_progress') AS active, "
            "COUNT(*) FILTER (WHERE status = 'done') AS done "
            "FROM agent_tasks WHERE agent_id = $1",
            agent["id"],
        )

        text = (
            f"🤖 <b>{agent['display_name']}</b>\n"
            f"Slug: {agent['slug']}\n"
            f"Роль: {agent['role']}\n"
            f"Активен: {'да' if agent['is_active'] else 'нет'}\n"
            f"Расписание: {agent['heartbeat_cron']}\n\n"
            f"📊 Задачи: {task_counts['pending']} ожидает, "
            f"{task_counts['active']} в работе, {task_counts['done']} выполнено\n"
        )

        if beats:
            text += "\n⏱ Последние тики:\n"
            for b in beats:
                err = f" ❌ {b['error'][:50]}" if b["error"] else ""
                text += f"  {b['triggered_at']:%H:%M} — {b['duration_ms']}ms, ✅{b['tasks_completed']}{err}\n"

        await message.answer(text)
    except Exception as e:
        logger.error("cmd_agent_status_error", error=str(e))
        await message.answer("Ошибка.")
    finally:
        await conn.close()


@router.message(Command("goals"))
async def cmd_goals(message: Message) -> None:
    """List active goals."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала выполните /start.")
            return

        goals = await goal_tracker.get_goals(conn, user_id)
        if not goals:
            await message.answer("🎯 Целей пока нет. Создайте: /goal <описание>")
            return

        lines = ["🎯 <b>Ваши цели:</b>\n"]
        for g in goals:
            bar = _progress_bar(g["progress_pct"])
            lines.append(
                f"• <b>{g['title']}</b>\n"
                f"  {bar} {g['progress_pct']}% | {g['status']}"
            )

        await message.answer("\n".join(lines))
    except Exception as e:
        logger.error("cmd_goals_error", error=str(e))
        await message.answer("Ошибка.")
    finally:
        await conn.close()


@router.message(Command("goal"))
async def cmd_goal_create(message: Message) -> None:
    """Create a new goal: /goal <description>."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /goal <описание цели>")
        return

    title = parts[1].strip()
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала выполните /start.")
            return

        # Find an active agent to assign
        agent = await conn.fetchrow(
            "SELECT id, display_name FROM agent_configs "
            "WHERE user_id = $1 AND is_active = TRUE LIMIT 1",
            user_id,
        )
        if not agent:
            await message.answer("Нет активных агентов для выполнения цели.")
            return

        await message.answer("🎯 Создаю цель и декомпозирую на подзадачи...")

        goal_id = await goal_tracker.create_goal(conn, user_id, title)
        subtasks = await goal_tracker.decompose_goal(conn, goal_id, agent["id"])

        text = f"🎯 <b>Цель создана:</b> {title}\n\n"
        text += f"Агент: {agent['display_name']}\n"
        text += f"Подзадачи ({len(subtasks)}):\n"
        for i, st in enumerate(subtasks, 1):
            text += f"  {i}. {st.get('title', '?')}\n"

        await message.answer(text)
    except Exception as e:
        logger.error("cmd_goal_create_error", error=str(e))
        await message.answer("Ошибка при создании цели.")
    finally:
        await conn.close()


@router.message(Command("agent_cost"))
async def cmd_agent_cost(message: Message) -> None:
    """Show LLM cost summary."""
    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        if not user_id:
            await message.answer("Сначала выполните /start.")
            return

        daily = await cost_monitor.get_daily_cost(conn, user_id)

        text = (
            "💰 <b>Расходы на LLM (сегодня):</b>\n\n"
            f"Стоимость: ${float(daily['total_usd']):.4f}\n"
            f"Входные токены: {daily['total_input']:,}\n"
            f"Выходные токены: {daily['total_output']:,}\n"
            f"Вызовов: {daily['total_calls']}\n"
        )

        await message.answer(text)
    except Exception as e:
        logger.error("cmd_agent_cost_error", error=str(e))
        await message.answer("Ошибка.")
    finally:
        await conn.close()


def _progress_bar(pct: int, width: int = 10) -> str:
    filled = int(width * pct / 100)
    return "▓" * filled + "░" * (width - filled)
