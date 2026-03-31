"""ЮKassa — интеграция платежей.

Подписки: Free → Starter → Pro → Business.
HMAC-SHA256 подпись webhook для верификации.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()

YUKASSA_API = "https://api.yookassa.ru/v3"

TIERS = {
    "starter": {"price": 490, "name": "Starter", "description": "200 сообщений, 5 звонков, 50 файлов"},
    "pro": {"price": 1490, "name": "Pro", "description": "Безлимит сообщений, 30 звонков, 200 файлов"},
    "business": {"price": 4990, "name": "Business", "description": "Всё безлимитно, приоритетная поддержка"},
}


async def create_payment(
    user_id: str,
    tier: str,
    telegram_id: int,
    return_url: str = "",
) -> dict | None:
    """Create a YuKassa payment for subscription.

    Returns dict with: payment_id, confirmation_url.
    """
    if not settings.yukassa_shop_id or not settings.yukassa_secret_key:
        logger.warning("yukassa_not_configured")
        return None

    tier_info = TIERS.get(tier)
    if not tier_info:
        logger.error("invalid_tier", tier=tier)
        return None

    start = time.monotonic()

    try:
        import uuid
        idempotence_key = str(uuid.uuid4())

        payload = {
            "amount": {
                "value": f"{tier_info['price']:.2f}",
                "currency": "RUB",
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or settings.webhook_url.replace("/webhook", "/miniapp/"),
            },
            "description": f"PersonalAI Sergiy — {tier_info['name']}",
            "metadata": {
                "user_id": user_id,
                "tier": tier,
                "telegram_id": str(telegram_id),
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{YUKASSA_API}/payments",
                json=payload,
                auth=(settings.yukassa_shop_id, settings.yukassa_secret_key),
                headers={
                    "Idempotence-Key": idempotence_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start
        payment_id = data.get("id", "")
        confirmation_url = data.get("confirmation", {}).get("confirmation_url", "")

        logger.info(
            "payment_created",
            payment_id=payment_id,
            tier=tier,
            amount=tier_info["price"],
            elapsed_sec=round(elapsed, 2),
        )

        return {
            "payment_id": payment_id,
            "confirmation_url": confirmation_url,
            "amount": tier_info["price"],
            "tier": tier,
        }

    except Exception as e:
        logger.error("payment_create_error", error=str(e))
        return None


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify YuKassa webhook HMAC-SHA256 signature."""
    if not settings.yukassa_secret_key:
        return False

    expected = hmac.new(
        settings.yukassa_secret_key.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def get_payment_status(payment_id: str) -> dict | None:
    """Check payment status in YuKassa."""
    if not settings.yukassa_shop_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{YUKASSA_API}/payments/{payment_id}",
                auth=(settings.yukassa_shop_id, settings.yukassa_secret_key),
            )
            resp.raise_for_status()
            return resp.json()

    except Exception as e:
        logger.error("payment_status_error", payment_id=payment_id, error=str(e))
        return None


def format_tier_info(tier: str) -> str:
    """Format tier info for display."""
    info = TIERS.get(tier)
    if not info:
        return f"Тариф «{tier}» не найден."
    return f"<b>{info['name']}</b> — {info['price']} ₽/мес\n{info['description']}"


def format_all_tiers() -> str:
    """Format all available tiers."""
    lines = ["<b>📋 Тарифы PersonalAI Sergiy:</b>\n"]
    lines.append("🆓 <b>Free</b> — бесплатно\n50 сообщений, 10 файлов\n")
    for key, info in TIERS.items():
        lines.append(f"💎 <b>{info['name']}</b> — {info['price']} ₽/мес\n{info['description']}\n")
    return "\n".join(lines)
