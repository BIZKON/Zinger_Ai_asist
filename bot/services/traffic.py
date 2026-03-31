"""Яндекс.Карты — пробки по маршруту дом→офис.

Кэш в Redis: 15 мин.
"""

from __future__ import annotations

import json
import time

import httpx
import redis.asyncio as aioredis
import structlog

from bot.config import settings

logger = structlog.get_logger()

CACHE_TTL = 900  # 15 minutes

# Default route: example points in SPB (to be configured per user)
DEFAULT_ROUTE = {
    "origin": "59.9343,30.3351",      # Центр СПб
    "destination": "59.9500,30.3167",  # Петроградская сторона
}


async def get_traffic(
    origin: str | None = None,
    destination: str | None = None,
    redis_client: aioredis.Redis | None = None,
) -> dict | None:
    """Get traffic/route info between two points.

    Uses Yandex Maps Router API.
    Returns dict with: duration_min, duration_traffic_min, distance_km, jams_level.
    """
    if not settings.yandex_maps_key:
        logger.warning("yandex_maps_not_configured")
        return None

    origin = origin or DEFAULT_ROUTE["origin"]
    destination = destination or DEFAULT_ROUTE["destination"]

    # Check cache
    cache_key = f"traffic:{origin}:{destination}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.routing.yandex.net/v2/route",
                params={
                    "apikey": settings.yandex_maps_key,
                    "waypoints": f"{origin}|{destination}",
                    "mode": "driving",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start

        route = data.get("route", {})
        legs = route.get("legs", [{}])
        leg = legs[0] if legs else {}
        summary = leg.get("summary", {})

        duration = summary.get("duration", {}).get("value", 0)
        duration_traffic = summary.get("durationInTraffic", {}).get("value", 0)
        distance = summary.get("distance", {}).get("value", 0)

        # Estimate jams level (1-10 scale)
        if duration > 0 and duration_traffic > 0:
            ratio = duration_traffic / duration
            jams_level = min(10, max(1, int(ratio * 5)))
        else:
            jams_level = 0

        result = {
            "duration_min": round(duration / 60),
            "duration_traffic_min": round(duration_traffic / 60),
            "distance_km": round(distance / 1000, 1),
            "jams_level": jams_level,
        }

        logger.info("traffic_fetched", elapsed_sec=round(elapsed, 2))

        # Cache
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key, CACHE_TTL, json.dumps(result)
                )
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error("traffic_error", error=str(e))
        return None


def format_traffic(t: dict) -> str:
    """Format traffic info as human-readable string."""
    if not t:
        return "Данные о пробках недоступны."

    jams = t.get("jams_level", 0)
    if jams <= 3:
        status = "🟢 Свободно"
    elif jams <= 6:
        status = "🟡 Средние пробки"
    else:
        status = "🔴 Серьёзные пробки"

    return (
        f"🚗 Маршрут: {t['distance_km']} км\n"
        f"  Без пробок: {t['duration_min']} мин\n"
        f"  С пробками: {t['duration_traffic_min']} мин\n"
        f"  {status} (уровень {jams}/10)"
    )
