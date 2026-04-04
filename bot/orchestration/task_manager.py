"""Agent task CRUD and status transitions."""

from __future__ import annotations

from uuid import UUID

import asyncpg
import structlog

logger = structlog.get_logger()


async def create_task(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    agent_id: UUID,
    title: str,
    description: str | None = None,
    goal_id: UUID | None = None,
    priority: str = "medium",
    context: dict | None = None,
    due_at: str | None = None,
) -> UUID:
    """Create a new agent task and return its id."""
    row = await conn.fetchrow(
        """
        INSERT INTO agent_tasks
            (user_id, agent_id, goal_id, title, description, priority, context, due_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::timestamptz)
        RETURNING id
        """,
        user_id, agent_id, goal_id, title, description,
        priority, _json(context), due_at,
    )
    logger.info("agent_task_created", task_id=str(row["id"]), title=title)
    return row["id"]


async def get_pending_tasks(
    conn: asyncpg.Connection, agent_id: UUID,
) -> list[dict]:
    """Return pending/in_progress tasks for an agent."""
    rows = await conn.fetch(
        """
        SELECT * FROM agent_tasks
        WHERE agent_id = $1 AND status IN ('pending', 'in_progress')
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END,
            created_at
        """,
        agent_id,
    )
    return [dict(r) for r in rows]


async def update_status(
    conn: asyncpg.Connection,
    task_id: UUID,
    status: str,
    result: dict | None = None,
) -> None:
    """Update task status and optionally store result."""
    extra = ""
    params: list = [status, task_id]

    if status == "in_progress":
        extra = ", started_at = NOW()"
    elif status in ("done", "failed", "cancelled"):
        extra = ", completed_at = NOW()"

    if result is not None:
        extra += ", result = $3::jsonb"
        params.append(_json(result))

    await conn.execute(
        f"UPDATE agent_tasks SET status = $1, updated_at = NOW(){extra} WHERE id = $2",
        *params,
    )


async def get_task(conn: asyncpg.Connection, task_id: UUID) -> dict | None:
    row = await conn.fetchrow("SELECT * FROM agent_tasks WHERE id = $1", task_id)
    return dict(row) if row else None


async def list_tasks(
    conn: asyncpg.Connection,
    user_id: UUID,
    agent_id: UUID | None = None,
    status: str | None = None,
) -> list[dict]:
    """List tasks with optional filters."""
    query = "SELECT * FROM agent_tasks WHERE user_id = $1"
    params: list = [user_id]
    idx = 2

    if agent_id:
        query += f" AND agent_id = ${idx}"
        params.append(agent_id)
        idx += 1
    if status:
        query += f" AND status = ${idx}"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT 50"
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


async def retry_or_fail(conn: asyncpg.Connection, task_id: UUID) -> str:
    """Increment retry_count; set to failed if max exceeded."""
    row = await conn.fetchrow(
        "SELECT retry_count, max_retries FROM agent_tasks WHERE id = $1", task_id,
    )
    if not row:
        return "not_found"

    if row["retry_count"] + 1 >= row["max_retries"]:
        await update_status(conn, task_id, "failed",
                            result={"reason": "max_retries_exceeded"})
        return "failed"

    await conn.execute(
        "UPDATE agent_tasks SET retry_count = retry_count + 1, status = 'pending', "
        "updated_at = NOW() WHERE id = $1",
        task_id,
    )
    return "retrying"


def _json(data: dict | None) -> str:
    """Serialize dict to JSON string for asyncpg JSONB params."""
    import json
    return json.dumps(data or {}, ensure_ascii=False, default=str)
