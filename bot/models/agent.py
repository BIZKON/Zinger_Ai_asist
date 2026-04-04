"""Agent orchestration models."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SkillAction(BaseModel):
    id: str
    description: str
    handler: str
    params: dict[str, str] | None = None


class SkillConfig(BaseModel):
    name: str
    display_name: str
    description: str = ""
    required_settings: list[str] = []
    actions: list[SkillAction] = []
    llm_tools_schema: list[dict[str, Any]] = []


class AgentConfig(BaseModel):
    id: UUID
    user_id: UUID
    org_id: UUID | None = None
    slug: str
    display_name: str
    role: str = "worker"
    skills: list[str] = []
    system_prompt: str | None = None
    heartbeat_cron: str = "0 */2 * * *"
    is_active: bool = True
    config: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentTask(BaseModel):
    id: UUID
    user_id: UUID
    agent_id: UUID
    goal_id: UUID | None = None
    title: str
    description: str | None = None
    status: str = "pending"
    priority: str = "medium"
    context: dict[str, Any] = {}
    result: dict[str, Any] | None = None
    retry_count: int = 0
    max_retries: int = 3
    due_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class AgentGoal(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None = None
    strategy: str | None = None
    status: str = "active"
    progress_pct: int = 0
    deadline: datetime | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime | None = None


class HeartbeatEntry(BaseModel):
    id: UUID
    agent_id: UUID
    user_id: UUID
    triggered_at: datetime | None = None
    duration_ms: int | None = None
    tasks_created: int = 0
    tasks_completed: int = 0
    error: str | None = None


class CostEntry(BaseModel):
    user_id: UUID
    agent_id: UUID
    date: date
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    call_count: int = 0
