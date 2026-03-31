"""Claude Vision — анализ фотографий.

Использует Claude для анализа изображений:
  - Распознавание содержимого фото
  - Извлечение структуры из фото накладных
  - Описание сцен и объектов
"""

from __future__ import annotations

import base64
import time

import structlog
from anthropic import AsyncAnthropic

from bot.config import settings

logger = structlog.get_logger()

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def analyze_image(
    image_data: bytes,
    mime_type: str = "image/jpeg",
    prompt: str = "Опиши что на этом изображении. Если это документ — извлеки ключевые данные.",
    max_tokens: int = 1024,
) -> str | None:
    """Analyze an image using Claude Vision.

    Args:
        image_data: Image file bytes.
        mime_type: Image MIME type.
        prompt: Analysis prompt.
        max_tokens: Max response tokens.

    Returns:
        Analysis text or None on failure.
    """
    if not settings.anthropic_api_key:
        logger.warning("anthropic_not_configured")
        return None

    client = _get_client()
    start = time.monotonic()
    encoded = base64.b64encode(image_data).decode()

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": encoded,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        elapsed = time.monotonic() - start
        text = response.content[0].text if response.content else ""

        logger.info(
            "vision_analysis",
            text_length=len(text),
            elapsed_sec=round(elapsed, 2),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return text

    except Exception as e:
        logger.error("vision_error", error=str(e))
        return None


async def extract_document_data(
    image_data: bytes,
    mime_type: str = "image/jpeg",
) -> str | None:
    """Extract structured data from a document photo (waybill, invoice, etc.)."""
    prompt = (
        "Это фото документа. Извлеки все ключевые данные:\n"
        "- Тип документа\n"
        "- Номер документа\n"
        "- Дата\n"
        "- Контрагент\n"
        "- Сумма\n"
        "- Другие важные поля\n\n"
        "Ответь структурированно. Если чего-то не видно — укажи."
    )
    return await analyze_image(image_data, mime_type, prompt)
