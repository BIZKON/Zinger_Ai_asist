"""Goal management: create, decompose via LLM, track progress."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
import structlog

from bot.orchestration import task_manager
from bot.orchestration.skills import get_agent_skills, load_skills
from bot.services.llm import chat_with_usage

logger = structlog.get_logger()

_DECOMPOSE_SYSTEM = """Ты — планировщик задач для AI-агента.
Пользователь ставит цель. Разбей её на конкретные подзадачи.
Доступные навыки агента: {skills}

Ответь ТОЛЬКО валидным JSON-массивом подзадач:
[
  {{"title": "...", "description": "...", "priority": "medium", "skill": "skill_name_or_null"}}
]
Без markdown, без пояснений. 3-7 подзадач."""


async def create_goal(
    conn: asyncpg.Connection,
    user_id: UUID,
    title: str,
    description: str | None = None,
    deadline: str | None = None,
) -> UUID:
    """Create a new goal."""
    row = await conn.fetchrow(
        """
        INSERT INTO agent_goals (user_id, title, description, deadline)
        VALUES ($1, $2, $3, $4::timestamptz)
        RETURNING id
        """,
        user_id, title, description, deadline,
    )
    logger.info("goal_created", goal_id=str(row["id"]), title=title)
    return row["id"]


async def decompose_goal(
    conn: asyncpg.Connection,
    goal_id: UUID,
    agent_id: UUID,
) -> list[dict]:
    """Use LLM to decompose a goal into agent_tasks."""
    goal = await conn.fetchrow("SELECT * FROM agent_goals WHERE id = $1", goal_id)
    if not goal:
        return []

    agent = await conn.fetchrow("SELECT * FROM agent_configs WHERE id = $1", agent_id)
    if not agent:
        return []

    # Build skill names list
    agent_skill_names = json.loads(agent["skills"]) if isinstance(agent["skills"], str) else agent["skills"]
    skills = get_agent_skills(agent_skill_names)
    skill_desc = ", ".join(f"{s.name} ({s.display_name})" for s in skills) or "нет навыков"

    prompt = f"Цель: {goal['title']}"
    if goal["description"]:
        prompt += f"\nОписание: {goal['description']}"

    system = _DECOMPOSE_SYSTEM.format(skills=skill_desc)
    result = await chat_with_usage(
        [{"role": "user", "content": prompt}],
        system_prompt=system,
        complexity="complex",
        max_tokens=1024,
    )

    # Parse LLM response
    try:
        subtasks = json.loads(result.text)
    except json.JSONDecodeError:
        logger.error("goal_decompose_json_error", text=result.text[:200])
        subtasks = [{"title": goal["title"], "priority": "medium"}]

    # Save strategy
    await conn.execute(
        "UPDATE agent_goals SET strategy = $1, updated_at = NOW() WHERE id = $2",
        result.text, goal_id,
    )

    # Create agent_tasks from subtasks
    created = []
    for st in subtasks:
        task_id = await task_manager.create_task(
            conn,
            user_id=goal["user_id"],
            agent_id=agent_id,
            goal_id=goal_id,
            title=st.get("title", "Подзадача"),
            description=st.get("description"),
            priority=st.get("priority", "medium"),
            context={"skill": st.get("skill")},
        )
        created.append({"id": str(task_id), **st})

    logger.info("goal_decomposed", goal_id=str(goal_id), subtasks=len(created))
    return created


async def update_progress(conn: asyncpg.Connection, goal_id: UUID) -> int:
    """Recalculate progress_pct from child tasks."""
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status IN ('done', 'cancelled')) AS completed
        FROM agent_tasks WHERE goal_id = $1
        """,
        goal_id,
    )
    total = row["total"]
    pct = int(row["completed"] / total * 100) if total > 0 else 0

    status = "completed" if pct == 100 else "active"
    await conn.execute(
        "UPDATE agent_goals SET progress_pct = $1, status = $2, updated_at = NOW() WHERE id = $3",
        pct, status, goal_id,
    )
    return pct


async def get_goals(
    conn: asyncpg.Connection,
    user_id: UUID,
    status: str | None = None,
) -> list[dict]:
    """List goals for a user."""
    if status:
        rows = await conn.fetch(
            "SELECT * FROM agent_goals WHERE user_id = $1 AND status = $2 ORDER BY created_at DESC",
            user_id, status,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM agent_goals WHERE user_id = $1 ORDER BY created_at DESC LIMIT 20",
            user_id,
        )
    return [dict(r) for r in rows]
