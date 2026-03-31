"""Deepgram STT для real-time звонков.

Использует WebSocket API Deepgram для streaming transcription.
Поддержка русского языка (model=nova-2, language=ru).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import structlog

from bot.config import settings

logger = structlog.get_logger()

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class RealtimeSTT:
    """Real-time Speech-to-Text via Deepgram WebSocket."""

    def __init__(self, on_transcript: asyncio.coroutines = None):
        """
        Args:
            on_transcript: async callback(text: str, is_final: bool)
        """
        self.on_transcript = on_transcript
        self._ws = None
        self._task: asyncio.Task | None = None

    async def connect(self) -> bool:
        """Establish WebSocket connection to Deepgram."""
        if not settings.deepgram_api_key:
            logger.warning("deepgram_not_configured")
            return False

        try:
            import websockets

            url = (
                f"{DEEPGRAM_WS_URL}"
                f"?model=nova-2&language=ru&smart_format=true"
                f"&interim_results=true&utterance_end_ms=1000"
                f"&encoding=linear16&sample_rate=16000&channels=1"
            )

            self._ws = await websockets.connect(
                url,
                additional_headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                },
            )
            self._task = asyncio.create_task(self._receive_loop())
            logger.info("deepgram_stt_connected")
            return True

        except Exception as e:
            logger.error("deepgram_stt_connect_error", error=str(e))
            return False

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send audio chunk to Deepgram for transcription."""
        if self._ws:
            try:
                await self._ws.send(audio_chunk)
            except Exception as e:
                logger.warning("deepgram_send_error", error=str(e))

    async def close(self) -> None:
        """Close the connection."""
        if self._ws:
            try:
                # Send close message
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
        logger.debug("deepgram_stt_closed")

    async def _receive_loop(self) -> None:
        """Receive and process transcription results."""
        try:
            async for message in self._ws:
                data = json.loads(message)

                if data.get("type") == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])

                    if alternatives:
                        transcript = alternatives[0].get("transcript", "")
                        is_final = data.get("is_final", False)

                        if transcript and self.on_transcript:
                            await self.on_transcript(transcript, is_final)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("deepgram_receive_error", error=str(e))


async def transcribe_audio_bytes(
    audio_data: bytes,
    mime_type: str = "audio/ogg",
) -> str | None:
    """Transcribe audio bytes (non-streaming, for recorded audio).

    Used for voice messages and recorded calls.
    """
    if not settings.deepgram_api_key:
        return None

    try:
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
                    "Content-Type": mime_type,
                },
                content=audio_data,
            )
            resp.raise_for_status()
            data = resp.json()

        transcript = (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )
        return transcript if transcript else None

    except Exception as e:
        logger.error("stt_batch_error", error=str(e))
        return None
