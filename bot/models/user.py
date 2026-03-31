"""User model."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class User(BaseModel):
    id: UUID
    telegram_id: int
    name: str | None = None
    city: str = "Санкт-Петербург"
    timezone: str = "Europe/Moscow"
    persona: str = "sergiy"
    voice_id: str = "Maxim"
    tier: str = "free"
    created_at: datetime | None = None
