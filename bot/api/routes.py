"""API routes для Telegram Mini App.

Endpoints:
  GET  /api/user/profile     — профиль пользователя
  POST /api/user/persona     — сменить персонажа
  POST /api/user/settings    — обновить настройки
  GET  /api/user/stats       — статистика использования
  GET  /api/user/media       — архив медиа
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from bot.api.auth import get_current_user
from bot.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/user", tags=["user"])


# ── Pydantic schemas ──

class PersonaUpdate(BaseModel):
    persona: str


class SettingsUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    timezone: str | None = None
    family: str | None = None
    auto: str | None = None
    sport: str | None = None
    quiet_hours_from: str | None = None
    quiet_hours_to: str | None = None


class ProfileResponse(BaseModel):
    id: str
    telegram_id: int
    name: str | None
    city: str | None
    persona: str
    voice_id: str
    tier: str
    timezone: str | None


class StatsResponse(BaseModel):
    messages: int = 0
    tasks_done: int = 0
    calls: int = 0
    files: int = 0
    tokens_used: int = 0


class MediaItem(BaseModel):
    id: str
    file_type: str | None
    original_filename: str | None
    extracted_text: str | None
    created_at: str | None


# ── Helper ──

async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(settings.database_url_raw)


async def _get_db_user(conn: asyncpg.Connection, telegram_id: int) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id, telegram_id, name, city, persona, voice_id, tier, timezone "
        "FROM users WHERE telegram_id = $1",
        telegram_id,
    )
    return dict(row) if row else None


# ── Endpoints ──

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(tg_user: dict = Depends(get_current_user)):
    """Получить профиль пользователя."""
    conn = await _get_conn()
    try:
        user = await _get_db_user(conn, tg_user["id"])
        if not user:
            return ProfileResponse(
                id="", telegram_id=tg_user["id"], name=tg_user.get("first_name"),
                city=None, persona="sergiy", voice_id="Maxim", tier="free", timezone=None,
            )

        return ProfileResponse(
            id=str(user["id"]),
            telegram_id=user["telegram_id"],
            name=user["name"],
            city=user["city"],
            persona=user["persona"] or "sergiy",
            voice_id=user["voice_id"] or "Maxim",
            tier=user["tier"] or "free",
            timezone=user["timezone"],
        )
    finally:
        await conn.close()


@router.post("/persona")
async def update_persona(
    body: PersonaUpdate,
    tg_user: dict = Depends(get_current_user),
):
    """Сменить персонажа."""
    valid_personas = {"sergiy", "serena", "viktor", "max"}
    if body.persona not in valid_personas:
        return {"ok": False, "error": f"Unknown persona: {body.persona}"}

    conn = await _get_conn()
    try:
        # Map persona to voice
        voice_map = {"sergiy": "Maxim", "serena": "Elena", "viktor": "Ivan", "max": "Stanislav"}

        await conn.execute(
            "UPDATE users SET persona = $1, voice_id = $2, updated_at = NOW() "
            "WHERE telegram_id = $3",
            body.persona, voice_map.get(body.persona, "Maxim"), tg_user["id"],
        )

        logger.info("persona_updated", telegram_id=tg_user["id"], persona=body.persona)
        return {"ok": True, "persona": body.persona}
    finally:
        await conn.close()


@router.post("/settings")
async def update_settings(
    body: SettingsUpdate,
    tg_user: dict = Depends(get_current_user),
):
    """Обновить настройки профиля."""
    conn = await _get_conn()
    try:
        user = await _get_db_user(conn, tg_user["id"])
        if not user:
            return {"ok": False, "error": "User not found"}

        user_id = str(user["id"])

        # Update users table
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.city is not None:
            updates["city"] = body.city
        if body.timezone is not None:
            updates["timezone"] = body.timezone

        if updates:
            set_parts = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
            set_parts.append(f"updated_at = NOW()")
            sql = f"UPDATE users SET {', '.join(set_parts)} WHERE telegram_id = $1"
            await conn.execute(sql, tg_user["id"], *updates.values())

        # Save preferences as structured memory facts
        from bot.services.memory import save_fact

        if body.family is not None:
            await save_fact(conn, user_id, "family", "описание", body.family)
        if body.auto is not None:
            await save_fact(conn, user_id, "auto", "автомобиль", body.auto)
        if body.sport is not None:
            await save_fact(conn, user_id, "sport", "вид_спорта", body.sport)
        if body.quiet_hours_from is not None:
            await save_fact(conn, user_id, "preferences", "тихие_часы_с", body.quiet_hours_from)
        if body.quiet_hours_to is not None:
            await save_fact(conn, user_id, "preferences", "тихие_часы_до", body.quiet_hours_to)

        logger.info("settings_updated", telegram_id=tg_user["id"])
        return {"ok": True}
    finally:
        await conn.close()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    period: str = Query("month", regex="^(week|month)$"),
    tg_user: dict = Depends(get_current_user),
):
    """Получить статистику использования."""
    conn = await _get_conn()
    try:
        user = await _get_db_user(conn, tg_user["id"])
        if not user:
            return StatsResponse()

        user_id = str(user["id"])
        now = datetime.now(timezone.utc)

        if period == "week":
            since = now - timedelta(days=7)
        else:
            since = now - timedelta(days=30)

        # Count tasks done
        tasks_done = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks "
            "WHERE user_id = $1::uuid AND status = 'done' AND updated_at >= $2",
            user_id, since,
        ) or 0

        # Count calls
        calls = await conn.fetchval(
            "SELECT COUNT(*) FROM call_sessions "
            "WHERE user_id = $1::uuid AND created_at >= $2",
            user_id, since,
        ) or 0

        # Count files
        files = await conn.fetchval(
            "SELECT COUNT(*) FROM media_archive "
            "WHERE user_id = $1::uuid AND created_at >= $2",
            user_id, since,
        ) or 0

        # Count episodic memories as proxy for messages
        messages = await conn.fetchval(
            "SELECT COUNT(*) FROM memory_episodic "
            "WHERE user_id = $1::uuid AND created_at >= $2",
            user_id, since,
        ) or 0

        return StatsResponse(
            messages=messages,
            tasks_done=tasks_done,
            calls=calls,
            files=files,
            tokens_used=0,  # TODO: track token usage
        )
    finally:
        await conn.close()


@router.get("/media")
async def get_media(
    search: str = Query("", max_length=200),
    file_type: str = Query("all", max_length=20),
    limit: int = Query(50, ge=1, le=100),
    tg_user: dict = Depends(get_current_user),
):
    """Получить список медиа из архива."""
    conn = await _get_conn()
    try:
        user = await _get_db_user(conn, tg_user["id"])
        if not user:
            return {"items": []}

        user_id = str(user["id"])

        # Build query
        conditions = ["user_id = $1::uuid"]
        params: list = [user_id]
        idx = 2

        if file_type != "all":
            conditions.append(f"file_type = ${idx}")
            params.append(file_type)
            idx += 1

        if search:
            conditions.append(
                f"(original_filename ILIKE ${idx} OR extracted_text ILIKE ${idx})"
            )
            params.append(f"%{search}%")
            idx += 1

        where = " AND ".join(conditions)
        params.append(limit)

        rows = await conn.fetch(
            f"SELECT id, file_type, original_filename, "
            f"LEFT(extracted_text, 200) as extracted_text, created_at "
            f"FROM media_archive WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ${idx}",
            *params,
        )

        items = [
            MediaItem(
                id=str(r["id"]),
                file_type=r["file_type"],
                original_filename=r["original_filename"],
                extracted_text=r["extracted_text"],
                created_at=r["created_at"].isoformat() if r["created_at"] else None,
            ).model_dump()
            for r in rows
        ]

        return {"items": items}
    finally:
        await conn.close()
