"""FastAPI WebSocket hub для голосовых звонков.

Запускается параллельно с ботом на порту 8001.
WebSocket /voice/stream:
  audio in → Deepgram STT → Claude dialog → ElevenLabs TTS → audio out

Usage:
  python -m bot.call_engine.orchestrator
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from bot.call_engine.deepgram_stt import RealtimeSTT
from bot.call_engine.dialog_manager import CallDialogManager
from bot.config import settings
from bot.services.voice_tts import text_to_speech

logger = structlog.get_logger()

app = FastAPI(title="PersonalAI Voice Engine")


@app.websocket("/voice/stream")
async def voice_stream(ws: WebSocket) -> None:
    """Handle a voice call session over WebSocket.

    Protocol:
      Client sends:
        {"type": "start", "user_id": "...", "contact_name": "...",
         "contact_phone": "...", "script_type": "manual", "context": "..."}
        {"type": "audio", "data": "<base64 PCM>"}
        {"type": "end"}

      Server sends:
        {"type": "greeting", "audio": "<base64 MP3>", "text": "..."}
        {"type": "response", "audio": "<base64 MP3>", "text": "..."}
        {"type": "end", "summary": "...", "session_id": "..."}
    """
    await ws.accept()
    logger.info("voice_ws_connected")

    dialog: CallDialogManager | None = None
    stt: RealtimeSTT | None = None
    pending_text: list[str] = []
    text_ready = asyncio.Event()

    async def on_transcript(text: str, is_final: bool) -> None:
        """Called when Deepgram produces a transcript."""
        if is_final and text.strip():
            pending_text.append(text.strip())
            text_ready.set()

    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start":
                # Initialize call session
                user_id = msg.get("user_id", "")
                dialog = CallDialogManager(
                    user_id=user_id,
                    user_name=msg.get("user_name", ""),
                    contact_name=msg.get("contact_name", ""),
                    script_type=msg.get("script_type", "manual"),
                    script_context=msg.get("context", ""),
                )

                # Connect real-time STT
                stt = RealtimeSTT(on_transcript=on_transcript)
                await stt.connect()

                # Send greeting
                greeting = await dialog.get_greeting()
                audio = await text_to_speech(greeting)

                import base64
                await ws.send_json({
                    "type": "greeting",
                    "text": greeting,
                    "audio": base64.b64encode(audio).decode() if audio else "",
                })

            elif msg_type == "audio" and stt:
                # Forward audio to STT
                import base64
                audio_data = base64.b64decode(msg.get("data", ""))
                await stt.send_audio(audio_data)

                # Check if we have a complete utterance
                if pending_text:
                    text_ready.clear()
                    utterance = " ".join(pending_text)
                    pending_text.clear()

                    # Generate AI response
                    if dialog:
                        reply = await dialog.process_utterance(utterance)
                        audio = await text_to_speech(reply)

                        await ws.send_json({
                            "type": "response",
                            "text": reply,
                            "audio": base64.b64encode(audio).decode() if audio else "",
                        })

            elif msg_type == "end":
                # End call, save session
                if stt:
                    await stt.close()

                summary = ""
                session_id = ""
                if dialog:
                    summary = await dialog.summarize()

                    try:
                        conn = await asyncpg.connect(settings.database_url_raw)
                        try:
                            session_id = await dialog.save_session(
                                conn,
                                direction=msg.get("direction", "outbound"),
                                contact_phone=msg.get("contact_phone", ""),
                                outcome=msg.get("outcome", ""),
                            )
                        finally:
                            await conn.close()
                    except Exception as e:
                        logger.error("call_save_error", error=str(e))

                await ws.send_json({
                    "type": "end",
                    "summary": summary,
                    "session_id": session_id,
                })
                break

    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected")
    except Exception as e:
        logger.error("voice_ws_error", error=str(e))
    finally:
        if stt:
            await stt.close()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "voice-engine"}


def start_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the voice engine server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
