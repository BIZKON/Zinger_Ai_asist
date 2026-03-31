"""Telegram WebApp initData validation.

Валидирует подпись initData из Telegram Mini App,
чтобы убедиться что запрос действительно от Telegram.

Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs

import structlog
from fastapi import HTTPException, Request

from bot.config import settings

logger = structlog.get_logger()


def validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData and extract user info.

    Args:
        init_data: Raw initData string from Telegram.WebApp.initData

    Returns:
        Dict with user info (id, first_name, etc.) or None if invalid.
    """
    if not init_data or not settings.bot_token:
        return None

    try:
        parsed = parse_qs(init_data)

        # Extract hash
        received_hash = parsed.get("hash", [""])[0]
        if not received_hash:
            return None

        # Build data-check-string (sorted, without hash)
        data_pairs = []
        for key, values in parsed.items():
            if key != "hash":
                data_pairs.append(f"{key}={values[0]}")
        data_check_string = "\n".join(sorted(data_pairs))

        # Compute HMAC
        secret_key = hmac.new(
            b"WebAppData", settings.bot_token.encode(), hashlib.sha256
        ).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("invalid_init_data_signature")
            return None

        # Extract user
        user_raw = parsed.get("user", [""])[0]
        if user_raw:
            return json.loads(user_raw)

        return None

    except Exception as e:
        logger.warning("init_data_validation_error", error=str(e))
        return None


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and validate Telegram user from request.

    Reads initData from Authorization header or X-Telegram-Init-Data header.
    """
    init_data = (
        request.headers.get("X-Telegram-Init-Data", "")
        or request.headers.get("Authorization", "").removeprefix("Bearer ")
    )

    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram initData")

    user = validate_init_data(init_data)
    if not user:
        # In development, allow passing telegram_id directly
        if not settings.is_production:
            tg_id = request.headers.get("X-Telegram-Id", "")
            if tg_id and tg_id.isdigit():
                return {"id": int(tg_id), "first_name": "Dev"}

        raise HTTPException(status_code=401, detail="Invalid initData signature")

    return user
