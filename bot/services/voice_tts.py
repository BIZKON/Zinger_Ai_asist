"""ElevenLabs V3 — голосовые ответы (TTS).

Голоса: Maxim (default), Ivan, Stanislav.
Поддержка streaming для real-time звонков.
"""

from __future__ import annotations

import time

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# Known voice IDs (ElevenLabs multilingual voices)
VOICE_MAP: dict[str, str] = {
    "Maxim": "Maxim",
    "Ivan": "Ivan",
    "Stanislav": "Stanislav",
    "Elena": "Elena",
}


async def text_to_speech(
    text: str,
    voice_id: str = "Maxim",
    model_id: str = "eleven_multilingual_v2",
) -> bytes | None:
    """Convert text to speech audio (MP3 bytes).

    Args:
        text: Text to synthesize.
        voice_id: ElevenLabs voice ID or name from VOICE_MAP.
        model_id: ElevenLabs model (multilingual v2 for Russian).

    Returns:
        MP3 audio bytes or None on failure.
    """
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_not_configured")
        return None

    resolved_id = VOICE_MAP.get(voice_id, voice_id)
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ELEVENLABS_BASE}/text-to-speech/{resolved_id}",
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.3,
                    },
                },
            )
            resp.raise_for_status()

        elapsed = time.monotonic() - start
        audio_bytes = resp.content

        logger.info(
            "tts_complete",
            voice=resolved_id,
            text_len=len(text),
            audio_bytes=len(audio_bytes),
            elapsed_sec=round(elapsed, 2),
        )
        return audio_bytes

    except Exception as e:
        logger.error("tts_error", voice=resolved_id, error=str(e))
        return None


async def text_to_speech_stream(
    text: str,
    voice_id: str = "Maxim",
    model_id: str = "eleven_multilingual_v2",
):
    """Stream TTS audio chunks for real-time playback.

    Yields audio chunks (bytes) as they arrive from ElevenLabs.
    Used in the call engine for low-latency voice responses.
    """
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_not_configured")
        return

    resolved_id = VOICE_MAP.get(voice_id, voice_id)
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream(
                "POST",
                f"{ELEVENLABS_BASE}/text-to-speech/{resolved_id}/stream",
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                    "output_format": "pcm_16000",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    yield chunk

        elapsed = time.monotonic() - start
        logger.info("tts_stream_complete", voice=resolved_id, elapsed_sec=round(elapsed, 2))

    except Exception as e:
        logger.error("tts_stream_error", voice=resolved_id, error=str(e))
