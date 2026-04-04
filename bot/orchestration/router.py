"""Agent Router: dispatch agent ticks and user requests to skill handlers."""

from __future__ import annotations

import importlib
import json
import time
from typing import Any, Callable
from uuid import UUID

import asyncpg
import structlog
from aiogram import Bot

from bot.config import settings
from bot.orchestration import cost_monitor, task_manager
from bot.orchestration.skills import get_agent_skills, validate_skill_requirements
from bot.services.llm import chat_with_usage

logger = structlog.get_logger()

_ROUTER_SYSTEM = """Ты — диспетчер AI-агента. Тебе дана задача и список доступных действий.
Выбери одно действие для выполнения или ответь "skip" если действие не требуется.

Доступные действия:
{actions}

Ответь ТОЛЬКО валидным JSON:
{{"action_id": "...", "params": {{...}}}}
или
{{"action_id": "skip", "reason": "..."}}
"""


async def execute_agent_tick(
    agent_config_id: str, bot: Bot, conn: asyncpg.Connection,
) -> dict:
    """Main heartbeat entry point — process pending tasks for an agent."""
    t0 = time.monotonic()
    tasks_created = 0
    tasks_completed = 0
    error_text = None

    agent = await conn.fetchrow(
        "SELECT * FROM agent_configs WHERE id = $1::uuid", agent_config_id,
    )
    if not agent or not agent["is_active"]:
        return {"status": "skipped", "reason": "inactive"}

    try:
        # Budget check
        budget = float((agent["config"] or {}).get(
            "daily_budget_usd", settings.agent_default_budget_usd,
        ))
        if not await cost_monitor.check_budget(
            conn, agent["user_id"], agent["id"], budget,
        ):
            logger.warning("agent_over_budget", agent=agent["slug"])
            return {"status": "over_budget"}

        # Get pending tasks
        pending = await task_manager.get_pending_tasks(conn, agent["id"])

        for task in pending[:5]:  # process max 5 tasks per tick
            try:
                result = await execute_single_task(conn, task, dict(agent), bot)
                if result.get("status") == "done":
                    tasks_completed += 1
            except Exception as e:
                logger.error("task_execution_error", task_id=str(task["id"]), error=str(e))
                await task_manager.retry_or_fail(conn, task["id"])

    except Exception as e:
        error_text = str(e)
        logger.error("agent_tick_error", agent=agent["slug"], error=error_text)

    duration_ms = int((time.monotonic() - t0) * 1000)

    # Log heartbeat
    await conn.execute(
        """
        INSERT INTO heartbeat_log
            (agent_id, user_id, duration_ms, tasks_created, tasks_completed, error)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        agent["id"], agent["user_id"], duration_ms,
        tasks_created, tasks_completed, error_text,
    )

    return {
        "status": "ok" if not error_text else "error",
        "duration_ms": duration_ms,
        "tasks_completed": tasks_completed,
    }


async def execute_single_task(
    conn: asyncpg.Connection,
    task: dict,
    agent: dict,
    bot: Bot,
) -> dict:
    """Execute one agent task using skill routing."""
    await task_manager.update_status(conn, task["id"], "in_progress")

    # Resolve agent skills
    agent_skill_names = agent["skills"] if isinstance(agent["skills"], list) else json.loads(agent["skills"])
    skills = get_agent_skills(agent_skill_names)

    # Build action list for LLM
    actions = []
    for skill in skills:
        if not validate_skill_requirements(skill):
            continue
        for action in skill.actions:
            actions.append(
                f"- {skill.name}/{action.id}: {action.description}"
                + (f" (params: {action.params})" if action.params else "")
            )

    if not actions:
        await task_manager.update_status(
            conn, task["id"], "failed",
            result={"reason": "no_available_actions"},
        )
        return {"status": "failed"}

    # Ask LLM to decide which action to take
    prompt = f"Задача: {task['title']}"
    if task.get("description"):
        prompt += f"\nОписание: {task['description']}"
    if task.get("context"):
        ctx = task["context"] if isinstance(task["context"], dict) else json.loads(task["context"])
        if ctx:
            prompt += f"\nКонтекст: {json.dumps(ctx, ensure_ascii=False)}"

    system = _ROUTER_SYSTEM.format(actions="\n".join(actions))
    llm_result = await chat_with_usage(
        [{"role": "user", "content": prompt}],
        system_prompt=system,
        complexity="medium",
        max_tokens=512,
    )

    # Track cost
    await cost_monitor.record_usage(
        conn,
        user_id=task["user_id"],
        agent_id=task["agent_id"],
        model=llm_result.model,
        input_tokens=llm_result.input_tokens,
        output_tokens=llm_result.output_tokens,
    )

    # Parse decision
    try:
        decision = json.loads(llm_result.text)
    except json.JSONDecodeError:
        await task_manager.update_status(
            conn, task["id"], "failed",
            result={"reason": "invalid_llm_response", "raw": llm_result.text[:500]},
        )
        return {"status": "failed"}

    action_id = decision.get("action_id", "skip")
    if action_id == "skip":
        await task_manager.update_status(
            conn, task["id"], "done",
            result={"action": "skip", "reason": decision.get("reason", "")},
        )
        return {"status": "done"}

    # Find and execute the handler
    handler_path = None
    for skill in skills:
        for action in skill.actions:
            if f"{skill.name}/{action.id}" == action_id or action.id == action_id:
                handler_path = action.handler
                break
        if handler_path:
            break

    if not handler_path:
        await task_manager.update_status(
            conn, task["id"], "failed",
            result={"reason": f"action_not_found: {action_id}"},
        )
        return {"status": "failed"}

    # Execute handler
    try:
        handler = await _resolve_handler(handler_path)
        params = decision.get("params", {})
        exec_result = await handler(**params) if params else await handler()
        await task_manager.update_status(
            conn, task["id"], "done",
            result={"action": action_id, "output": str(exec_result)[:2000]},
        )
        return {"status": "done"}
    except Exception as e:
        logger.error("handler_error", handler=handler_path, error=str(e))
        status = await task_manager.retry_or_fail(conn, task["id"])
        return {"status": status}


async def _resolve_handler(dotted_path: str) -> Callable:
    """Dynamically import a handler function from dotted path."""
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid handler path: {dotted_path}")
    module_path, func_name = parts
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


async def route_user_request(
    conn: asyncpg.Connection, user_id: UUID, text: str, bot: Bot,
) -> str:
    """Route an explicit user request to an agent."""
    agents = await conn.fetch(
        "SELECT * FROM agent_configs WHERE user_id = $1 AND is_active = TRUE",
        user_id,
    )
    if not agents:
        return "У вас нет активных агентов. Создайте агента через настройки."

    # Use first active agent
    agent = dict(agents[0])
    task_id = await task_manager.create_task(
        conn,
        user_id=user_id,
        agent_id=agent["id"],
        title=text[:200],
        description=text,
        priority="high",
    )

    task = await task_manager.get_task(conn, task_id)
    result = await execute_single_task(conn, task, agent, bot)
    return f"Агент {agent['display_name']}: задача {'выполнена' if result['status'] == 'done' else 'в обработке'}."


async def stub_handler(**kwargs: Any) -> str:
    """Stub handler for skills not yet implemented."""
    logger.info("stub_handler_called", params=kwargs)
    return "Функция в разработке."
