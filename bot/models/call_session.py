"""Call session model (§12 Voice Call Engine)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CallSession(BaseModel):
    id: UUID
    user_id: UUID
    direction: str | None = None
    contact_phone: str | None = None
    contact_name: str | None = None
    script_type: str | None = None
    transcript: str | None = None
    summary: str | None = None
    outcome: str | None = None
    duration_sec: int | None = None
    created_at: datetime | None = None
