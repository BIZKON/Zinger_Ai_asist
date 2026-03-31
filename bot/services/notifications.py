"""Проактивные алерты — 42 сценария из PRD v6 §5.

Категории:
  - Семья: ДР, школа, годовщина
  - Авто: ТО, ОСАГО, смена резины
  - Спорт: тренировки, результаты
  - Еда: обед по локации, аллергия-защита (КРИТИЧНО)
  - Здоровье: вода, сон
  - Работа: встречи, дедлайны, 1С алерты
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import asyncpg
import redis.asyncio as aioredis
import structlog
from aiogram import Bot

from bot.config import settings
from bot.services import llm
from bot.services.persona import build_system_prompt
from bot.services.weather import get_weather

logger = structlog.get_logger()


class Alert(NamedTuple):
    user_telegram_id: int
    text: str
    priority: str  # low | medium | high | critical


# ── Scenario registry ──

SCENARIOS: list[dict] = [
    # Семья
    {"id": "family_birthday", "category": "family", "fact_key": "день_рождения",
     "days_before": [7, 3, 1, 0], "template": "🎂 {fact} через {days} дн. Идеи подарков?"},
    {"id": "family_anniversary", "category": "family", "fact_key": "годовщина",
     "days_before": [7, 1, 0], "template": "💍 Годовщина {fact} через {days} дн."},
    {"id": "family_school", "category": "family", "fact_key": "школа",
     "days_before": [1], "template": "🏫 Завтра: {fact}"},

    # Авто
    {"id": "auto_maintenance", "category": "auto", "fact_key": "ТО_дата",
     "days_before": [14, 7, 1], "template": "🔧 ТО через {days} дн. Записаться в сервис?"},
    {"id": "auto_insurance", "category": "auto", "fact_key": "ОСАГО_дата",
     "days_before": [30, 14, 7, 1], "template": "📋 ОСАГО истекает через {days} дн."},

    # Здоровье
    {"id": "health_water", "category": "health", "interval_hours": 2,
     "template": "💧 Выпей воды. Прошло {hours}ч с последнего напоминания."},
    {"id": "health_sleep", "category": "health", "after_hour": 23,
     "template": "🌙 Уже {hour}:00. Пора спать, завтра рабочий день."},

    # Работа
    {"id": "work_meeting", "category": "work", "fact_key": "встреча",
     "minutes_before": [40, 10], "template": "📅 Встреча через {minutes} мин: {fact}"},
]


async def check_date_scenarios(
    conn: asyncpg.Connection,
    bot: Bot,
) -> list[Alert]:
    """Check all date-based scenarios for all users.

    Should be called by a cron every hour.
    """
    alerts: list[Alert] = []
    today = datetime.now(timezone.utc).date()

    users = await conn.fetch("SELECT id, telegram_id, name, persona FROM users")

    for user in users:
        user_id = str(user["id"])

        # Get user's date-based facts
        facts = await conn.fetch(
            "SELECT category, key, value FROM memory_structured "
            "WHERE user_id = $1::uuid AND is_active = TRUE",
            user_id,
        )

        for scenario in SCENARIOS:
            if "days_before" not in scenario:
                continue

            fact_key = scenario.get("fact_key", "")
            matching_facts = [
                f for f in facts
                if f["category"] == scenario["category"]
                and fact_key.lower() in (f["key"] or "").lower()
            ]

            for fact in matching_facts:
                # Try to parse date from fact value
                target_date = _parse_date(fact["value"])
                if not target_date:
                    continue

                # Adjust for annual events (birthdays, anniversaries)
                target_this_year = target_date.replace(year=today.year)
                if target_this_year < today:
                    target_this_year = target_this_year.replace(year=today.year + 1)

                days_left = (target_this_year - today).days

                if days_left in scenario["days_before"]:
                    text = scenario["template"].format(
                        fact=fact["value"],
                        days=days_left,
                    )
                    alerts.append(Alert(
                        user_telegram_id=user["telegram_id"],
                        text=text,
                        priority="high" if days_left <= 1 else "medium",
                    ))

    return alerts


async def check_weather_alerts(
    conn: asyncpg.Connection,
    redis_client: aioredis.Redis | None = None,
) -> list[Alert]:
    """Check weather-based scenarios (tire change, rain alert, etc.)."""
    alerts: list[Alert] = []

    users = await conn.fetch("SELECT id, telegram_id, city FROM users")

    for user in users:
        city = user["city"] or "Санкт-Петербург"
        weather = await get_weather(city=city, redis_client=redis_client)

        if not weather:
            continue

        temp = weather.get("temp", 0)

        # Tire change alert: +7°C threshold
        if temp and 5 <= temp <= 9:
            # Check if user has auto facts
            has_auto = await conn.fetchval(
                "SELECT 1 FROM memory_structured "
                "WHERE user_id = $1 AND category = 'auto' AND is_active = TRUE LIMIT 1",
                user["id"],
            )
            if has_auto:
                alerts.append(Alert(
                    user_telegram_id=user["telegram_id"],
                    text=f"🔄 Температура {temp}°C. Пора менять резину?",
                    priority="medium",
                ))

    return alerts


async def send_alerts(bot: Bot, alerts: list[Alert]) -> int:
    """Send alerts to users. Returns number of successfully sent alerts."""
    sent = 0
    for alert in alerts:
        try:
            await bot.send_message(alert.user_telegram_id, alert.text)
            sent += 1
            logger.info(
                "alert_sent",
                telegram_id=alert.user_telegram_id,
                priority=alert.priority,
            )
        except Exception as e:
            logger.warning(
                "alert_send_error",
                telegram_id=alert.user_telegram_id,
                error=str(e),
            )
    return sent


async def run_notification_cycle(bot: Bot) -> None:
    """Run all notification checks. Called by scheduler every hour."""
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(settings.database_url_raw)
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

        all_alerts: list[Alert] = []

        # Date-based scenarios
        date_alerts = await check_date_scenarios(conn, bot)
        all_alerts.extend(date_alerts)

        # Weather-based alerts
        weather_alerts = await check_weather_alerts(conn, redis_client)
        all_alerts.extend(weather_alerts)

        if all_alerts:
            sent = await send_alerts(bot, all_alerts)
            logger.info("notification_cycle", total=len(all_alerts), sent=sent)

    except Exception as e:
        logger.error("notification_cycle_error", error=str(e))
    finally:
        if conn:
            await conn.close()


def _parse_date(value: str):
    """Try to parse a date from a fact value string."""
    import re
    from datetime import date

    if not value:
        return None

    # Try common formats
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m"):
        try:
            d = datetime.strptime(value.strip(), fmt).date()
            if d.year < 1900:
                d = d.replace(year=2000)
            return d
        except ValueError:
            continue

    # Try to find date pattern in text
    match = re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", value)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else 2000
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass

    return None
