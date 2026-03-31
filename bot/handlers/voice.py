"""Handler: голосовые сообщения → Deepgram STT → текст → LLM."""

from __future__ import annotations

import io
import time

import httpx
import structlog
from aiogram import Bot, Router
from aiogram.types import Message

from bot.config import settings

logger = structlog.get_logger()

router = Router()


async def transcribe_voice(bot: Bot, message: Message) -> str | None:
    """Download voice message from Telegram and transcribe via Deepgram.

    Returns transcribed text or None on failure.
    """
    if not settings.deepgram_api_key:
        logger.warning("deepgram_not_configured")
        return None

    try:
        # Download voice file from Telegram
        voice = message.voice or message.audio
        if not voice:
            return None

        file = await bot.get_file(voice.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        file_bytes.seek(0)

        # Send to Deepgram STT
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={
                    "model": "nova-2",
                    "language": "ru",
                    "smart_format": "true",
                },
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": "audio/ogg",
                },
                content=file_bytes.read(),
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start
        transcript = (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )

        logger.info(
            "stt_complete",
            duration_sec=round(elapsed, 2),
            text_length=len(transcript),
        )
        return transcript if transcript else None

    except Exception as e:
        logger.error("stt_error", error=str(e))
        return None


@router.message(lambda msg: msg.voice is not None or msg.audio is not None)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Process voice/audio messages: STT → treat as text."""
    # Transcribe
    text = await transcribe_voice(bot, message)

    if not text:
        await message.answer(
            "Не удалось распознать голосовое сообщение. "
            "Попробуй ещё раз или напиши текстом."
        )
        return

    # Show what was recognized
    await message.answer(f"🎤 <i>{text}</i>")

    # Now process as a text message — reuse chat handler logic
    from bot.handlers.chat import handle_text

    # Create a pseudo-message with the transcribed text
    message.text = text
    await handle_text(message)
