"""Yandex Vision OCR — распознавание текста на изображениях.

Используется для фото накладных, сканов документов.
"""

from __future__ import annotations

import base64
import time

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()


async def recognize_text(image_data: bytes) -> str | None:
    """Recognize text in an image using Yandex Vision OCR.

    Args:
        image_data: Image file bytes (JPEG, PNG).

    Returns:
        Extracted text or None on failure.
    """
    if not settings.yandex_vision_key:
        logger.warning("yandex_vision_not_configured")
        return None

    start = time.monotonic()
    encoded = base64.b64encode(image_data).decode()

    try:
        payload = {
            "mimeType": "image",
            "languageCodes": ["ru", "en"],
            "model": "page",
            "content": encoded,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText",
                headers={
                    "Authorization": f"Api-Key {settings.yandex_vision_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start

        # Extract text from response
        result = data.get("result", {})
        blocks = result.get("textAnnotation", {}).get("blocks", [])

        lines = []
        for block in blocks:
            for line in block.get("lines", []):
                text = line.get("text", "")
                if text.strip():
                    lines.append(text.strip())

        full_text = "\n".join(lines)

        logger.info(
            "ocr_complete",
            text_length=len(full_text),
            elapsed_sec=round(elapsed, 2),
        )
        return full_text if full_text else None

    except Exception as e:
        logger.error("ocr_error", error=str(e))
        return None
