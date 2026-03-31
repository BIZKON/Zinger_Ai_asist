"""Memory layer models."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class MemoryFact(BaseModel):
    """Structured memory — facts about the user."""
    id: UUID
    user_id: UUID
    category: str | None = None
    key: str | None = None
    value: str | None = None
    is_active: bool = True
    updated_at: datetime | None = None


class MemorySemantic(BaseModel):
    """Semantic memory — vector embeddings of conversations."""
    id: UUID
    user_id: UUID
    content: str | None = None
    source: str = "dialog"
    created_at: datetime | None = None


class MemoryEpisode(BaseModel):
    """Episodic memory — conversation summaries."""
    id: UUID
    user_id: UUID
    summary: str | None = None
    relevance_score: float = 1.0
    session_date: date | None = None
    created_at: datetime | None = None
