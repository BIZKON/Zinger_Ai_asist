"""LLM cost tracking and budget enforcement."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import asyncpg
import structlog

logger = structlog.get_logger()

# Price per 1K tokens (USD)
PRICE_PER_1K = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-sonnet-4-5-20250514": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
    "gemini-flash": {"input": 0.0, "output": 0.0},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a given model and token counts."""
    prices = PRICE_PER_1K.get(model, {"input": 0.003, "output": 0.015})
    return (
        input_tokens / 1000 * prices["input"]
        + output_tokens / 1000 * prices["output"]
    )


async def record_usage(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    agent_id: UUID,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """UPSERT daily cost aggregation."""
    cost = calculate_cost(model, input_tokens, output_tokens)

    await conn.execute(
        """
        INSERT INTO agent_cost_daily
            (user_id, agent_id, date, model, input_tokens, output_tokens, cost_usd, call_count)
        VALUES ($1, $2, CURRENT_DATE, $3, $4, $5, $6, 1)
        ON CONFLICT (user_id, agent_id, date, model)
        DO UPDATE SET
            input_tokens = agent_cost_daily.input_tokens + EXCLUDED.input_tokens,
            output_tokens = agent_cost_daily.output_tokens + EXCLUDED.output_tokens,
            cost_usd = agent_cost_daily.cost_usd + EXCLUDED.cost_usd,
            call_count = agent_cost_daily.call_count + 1
        """,
        user_id, agent_id, model, input_tokens, output_tokens, cost,
    )

    logger.debug(
        "cost_recorded",
        agent_id=str(agent_id), model=model,
        tokens=input_tokens + output_tokens, cost_usd=round(cost, 6),
    )


async def get_daily_cost(
    conn: asyncpg.Connection, user_id: UUID, day: date | None = None,
) -> dict:
    """Total cost for a user on a given day."""
    day = day or date.today()
    row = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(cost_usd), 0) AS total_usd,
            COALESCE(SUM(input_tokens), 0) AS total_input,
            COALESCE(SUM(output_tokens), 0) AS total_output,
            COALESCE(SUM(call_count), 0) AS total_calls
        FROM agent_cost_daily
        WHERE user_id = $1 AND date = $2
        """,
        user_id, day,
    )
    return dict(row)


async def get_agent_cost(
    conn: asyncpg.Connection, agent_id: UUID, days: int = 30,
) -> list[dict]:
    """Cost history for an agent over N days."""
    rows = await conn.fetch(
        """
        SELECT date, model, input_tokens, output_tokens, cost_usd, call_count
        FROM agent_cost_daily
        WHERE agent_id = $1 AND date >= CURRENT_DATE - $2::int
        ORDER BY date DESC
        """,
        agent_id, days,
    )
    return [dict(r) for r in rows]


async def check_budget(
    conn: asyncpg.Connection, user_id: UUID, agent_id: UUID,
    daily_budget_usd: float = 1.0,
) -> bool:
    """Return True if agent is within its daily budget."""
    cost = await get_daily_cost(conn, user_id)
    return float(cost["total_usd"]) < daily_budget_usd
