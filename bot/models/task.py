"""Task model."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Task(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    priority: str = "medium"
    status: str = "active"
    due_date: datetime | None = None
    source: str = "chat"
    created_at: datetime | None = None
