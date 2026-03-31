"""Deepgram STT для аудиофайлов (с диаризацией).

Обрабатывает аудиозаписи: голосовые заметки, записи совещаний.
Возвращает транскрипт и извлечённые задачи.
"""

from __future__ import annotations

import time

import httpx
import structlog

from bot.config import settings
from bot.services import llm

logger = structlog.get_logger()


async def transcribe_audio(
    audio_data: bytes,
    mime_type: str = "audio/ogg",
    diarize: bool = False,
) -> str | None:
    """Transcribe audio file via Deepgram.

    Args:
        audio_data: Audio file bytes.
        mime_type: Audio MIME type.
        diarize: Enable speaker diarization.

    Returns:
        Transcript text or None.
    """
    if not settings.deepgram_api_key:
        logger.warning("deepgram_not_configured")
        return None

    start = time.monotonic()

    try:
        params = {
            "model": "nova-2",
            "language": "ru",
            "smart_format": "true",
            "paragraphs": "true",
        }
        if diarize:
            params["diarize"] = "true"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": mime_type,
                },
                content=audio_data,
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.monotonic() - start

        if diarize:
            transcript = _format_diarized(data)
        else:
            transcript = (
                data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
            )

        logger.info(
            "audio_transcribed",
            text_length=len(transcript or ""),
            diarize=diarize,
            elapsed_sec=round(elapsed, 2),
        )
        return transcript if transcript else None

    except Exception as e:
        logger.error("audio_transcribe_error", error=str(e))
        return None


def _format_diarized(data: dict) -> str:
    """Format diarized transcript with speaker labels."""
    words = (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
        .get("words", [])
    )

    if not words:
        return ""

    lines = []
    current_speaker = None
    current_text = []

    for word in words:
        speaker = word.get("speaker", 0)
        if speaker != current_speaker:
            if current_text:
                lines.append(f"Спикер {current_speaker}: {' '.join(current_text)}")
            current_speaker = speaker
            current_text = []
        current_text.append(word.get("word", ""))

    if current_text:
        lines.append(f"Спикер {current_speaker}: {' '.join(current_text)}")

    return "\n".join(lines)


async def extract_tasks_from_transcript(transcript: str) -> str:
    """Use LLM to extract action items from a meeting transcript."""
    prompt = (
        "Из транскрипта совещания извлеки список задач и решений.\n"
        "Формат:\n"
        "📋 Задачи:\n"
        "1. [задача] — ответственный (если указан)\n\n"
        "💡 Решения:\n"
        "1. [решение]\n\n"
        f"Транскрипт:\n{transcript[:3000]}"
    )

    return await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        complexity="medium",
        max_tokens=500,
    )
