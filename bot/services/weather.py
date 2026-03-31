"""Яндекс.Погода API — температура, осадки, рассвет/закат.

Кэш в Redis: 30 мин.
"""

from __future__ import annotations

import json
import time

import httpx
import redis.asyncio as aioredis
import structlog

from bot.config import settings

logger = structlog.get_logger()

# City coordinates
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Санкт-Петербург": (59.9343, 30.3351),
    "Москва": (55.7558, 37.6173),
}

CACHE_TTL = 1800  # 30 minutes


async def get_weather(
    city: str = "Санкт-Петербург",
    redis_client: aioredis.Redis | None = None,
) -> dict | None:
    """Get current weather for a city.

    Returns dict with: temp, feels_like, condition, wind_speed, humidity,
    sunrise, sunset, or None on failure.
    """
    if not settings.yandex_weather_key:
        logger.warning("yandex_weather_not_configured")
        return None

    # Check cache
    cache_key = f"weather:{city}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    lat, lon = CITY_COORDS.get(city, CITY_COORDS["Санкт-Петербург"])
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.weather.yandex.ru/v2/forecast",
                params={"lat": lat, "lon": lon, "lang": "ru_RU", "limit": 1},
                headers={"X-Yandex-Weather-Key": settings.yandex_weather_key},
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start
        fact = data.get("fact", {})
        forecast_day = data.get("forecasts", [{}])[0]

        result = {
            "temp": fact.get("temp"),
            "feels_like": fact.get("feels_like"),
            "condition": _translate_condition(fact.get("condition", "")),
            "wind_speed": fact.get("wind_speed"),
            "humidity": fact.get("humidity"),
            "sunrise": forecast_day.get("sunrise"),
            "sunset": forecast_day.get("sunset"),
            "city": city,
        }

        logger.info("weather_fetched", city=city, elapsed_sec=round(elapsed, 2))

        # Cache result
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key, CACHE_TTL, json.dumps(result, ensure_ascii=False)
                )
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error("weather_error", city=city, error=str(e))
        return None


def format_weather(w: dict) -> str:
    """Format weather dict as a human-readable string."""
    if not w:
        return "Погода недоступна."

    parts = [f"🌡 {w['temp']}°C (ощущается {w['feels_like']}°C)"]

    if w.get("condition"):
        parts.append(f"  {w['condition']}")
    if w.get("wind_speed"):
        parts.append(f"  💨 Ветер {w['wind_speed']} м/с")
    if w.get("sunrise") and w.get("sunset"):
        parts.append(f"  🌅 {w['sunrise']} – 🌇 {w['sunset']}")

    return "\n".join(parts)


CONDITION_MAP = {
    "clear": "Ясно ☀️",
    "partly-cloudy": "Малооблачно ⛅",
    "cloudy": "Облачно с прояснениями 🌤",
    "overcast": "Пасмурно ☁️",
    "light-rain": "Небольшой дождь 🌦",
    "rain": "Дождь 🌧",
    "heavy-rain": "Сильный дождь 🌧",
    "showers": "Ливень ⛈",
    "wet-snow": "Дождь со снегом 🌨",
    "light-snow": "Небольшой снег 🌨",
    "snow": "Снег ❄️",
    "snow-showers": "Снегопад ❄️",
    "hail": "Град 🌨",
    "thunderstorm": "Гроза ⛈",
    "thunderstorm-with-rain": "Гроза с дождём ⛈",
    "thunderstorm-with-hail": "Гроза с градом ⛈",
}


def _translate_condition(condition: str) -> str:
    return CONDITION_MAP.get(condition, condition)
