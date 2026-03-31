"""FFmpeg keyframes + STT → саммари видео.

Обработка видео: извлечение аудио → STT → саммари.
Для кейфреймов — Claude Vision.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

import structlog

from bot.media_engine.audio_pipeline import transcribe_audio, extract_tasks_from_transcript

logger = structlog.get_logger()


async def extract_audio_from_video(video_data: bytes) -> bytes | None:
    """Extract audio track from video using FFmpeg.

    Returns audio bytes in OGG format or None on failure.
    """
    start = time.monotonic()

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_in:
            tmp_in.write(video_data)
            input_path = tmp_in.name

        output_path = input_path.replace(".mp4", ".ogg")

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", input_path,
            "-vn",  # no video
            "-acodec", "libopus",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            output_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.wait()

        elapsed = time.monotonic() - start

        if process.returncode != 0:
            logger.error("ffmpeg_error", returncode=process.returncode)
            return None

        with open(output_path, "rb") as f:
            audio_data = f.read()

        logger.info(
            "video_audio_extracted",
            audio_bytes=len(audio_data),
            elapsed_sec=round(elapsed, 2),
        )
        return audio_data

    except FileNotFoundError:
        logger.error("ffmpeg_not_found")
        return None
    except Exception as e:
        logger.error("video_extract_error", error=str(e))
        return None
    finally:
        for path in [input_path, output_path]:
            try:
                os.unlink(path)
            except (OSError, UnboundLocalError):
                pass


async def process_video(video_data: bytes) -> dict:
    """Full video processing pipeline.

    Returns dict with: transcript, tasks, summary.
    """
    result = {"transcript": None, "tasks": None, "summary": None}

    # Step 1: Extract audio
    audio = await extract_audio_from_video(video_data)
    if not audio:
        result["summary"] = "Не удалось извлечь аудио из видео."
        return result

    # Step 2: Transcribe
    transcript = await transcribe_audio(audio, mime_type="audio/ogg", diarize=True)
    result["transcript"] = transcript

    if not transcript:
        result["summary"] = "Не удалось распознать речь в видео."
        return result

    # Step 3: Extract tasks
    tasks = await extract_tasks_from_transcript(transcript)
    result["tasks"] = tasks
    result["summary"] = tasks  # Tasks summary serves as video summary

    return result
