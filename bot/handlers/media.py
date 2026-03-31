"""Handler: фото, документы, аудио → Media Intelligence Engine (§13).

Обрабатывает все медиа-сообщения из Telegram:
  - Фото → OCR + Claude Vision
  - Документы → PDF/DOCX/Excel/CSV парсинг
  - Аудио файлы → Deepgram STT → задачи
  - Видео → FFmpeg + STT → саммари
"""

from __future__ import annotations

import io

import asyncpg
import structlog
from aiogram import Bot, Router
from aiogram.types import Message

from bot.config import settings
from bot.media_engine.router import PipelineType, route_file

logger = structlog.get_logger()

router = Router()


async def _get_user_id(conn: asyncpg.Connection, telegram_id: int) -> str | None:
    row = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", telegram_id)
    return str(row["id"]) if row else None


async def _download_file(bot: Bot, file_id: str) -> tuple[bytes, str]:
    """Download file from Telegram. Returns (bytes, file_path)."""
    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)
    buf.seek(0)
    return buf.read(), file.file_path or ""


async def _save_to_archive(
    conn: asyncpg.Connection,
    user_id: str,
    file_type: str,
    filename: str,
    extracted_text: str,
) -> None:
    """Save processed media to archive."""
    await conn.execute(
        "INSERT INTO media_archive (user_id, file_type, original_filename, extracted_text) "
        "VALUES ($1::uuid, $2, $3, $4)",
        user_id, file_type, filename, extracted_text[:10000] if extracted_text else "",
    )


@router.message(lambda msg: msg.photo is not None)
async def handle_photo(message: Message, bot: Bot) -> None:
    """Process photo messages."""
    photo = message.photo[-1]  # Largest size
    file_data, _ = await _download_file(bot, photo.file_id)

    await message.answer("🔍 Анализирую фото...")

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)

        # Try OCR first
        from bot.media_engine.ocr import recognize_text
        ocr_text = await recognize_text(file_data)

        if ocr_text and len(ocr_text) > 20:
            # Document/scan detected — show OCR result
            response = f"📄 <b>Распознанный текст:</b>\n\n{ocr_text[:3000]}"

            # Also try Claude Vision for structured extraction
            from bot.media_engine.vision import extract_document_data
            structured = await extract_document_data(file_data)
            if structured:
                response += f"\n\n📋 <b>Данные документа:</b>\n{structured[:1000]}"
        else:
            # Regular photo — Claude Vision analysis
            from bot.media_engine.vision import analyze_image
            analysis = await analyze_image(file_data)
            response = analysis or "Не удалось проанализировать фото."

        await message.answer(response[:4000])

        if user_id:
            text = ocr_text or response
            await _save_to_archive(conn, user_id, "photo", "photo.jpg", text)

    except Exception as e:
        logger.error("photo_handler_error", error=str(e))
        await message.answer("Ошибка при обработке фото.")
    finally:
        await conn.close()


@router.message(lambda msg: msg.document is not None)
async def handle_document(message: Message, bot: Bot) -> None:
    """Process document messages (PDF, DOCX, Excel, CSV, etc.)."""
    doc = message.document
    filename = doc.file_name or "unknown"
    mime_type = doc.mime_type or ""

    file_info = route_file(filename, mime_type, doc.file_size or 0, doc.file_id)

    if file_info.pipeline == PipelineType.UNSUPPORTED:
        await message.answer(f"Формат файла «{filename}» не поддерживается.")
        return

    file_data, _ = await _download_file(bot, doc.file_id)
    await message.answer(f"📎 Обрабатываю: <b>{filename}</b>...")

    conn = await asyncpg.connect(settings.database_url_raw)
    try:
        user_id = await _get_user_id(conn, message.from_user.id)
        response = ""

        if file_info.pipeline == PipelineType.DOCUMENT:
            from bot.media_engine.doc_parser import parse_document
            text = await parse_document(file_data, filename)

            if text:
                # Summarize with LLM
                from bot.services import llm
                summary = await llm.chat(
                    messages=[{"role": "user", "content": f"Кратко перескажи этот документ (3-5 пунктов):\n\n{text[:3000]}"}],
                    complexity="medium",
                )
                response = f"📄 <b>{filename}</b>\n\n{summary}"
            else:
                response = f"Не удалось извлечь текст из {filename}."

        elif file_info.pipeline == PipelineType.TABLE:
            from bot.media_engine.table_parser import parse_table
            result = await parse_table(file_data, filename)
            response = result.get("text", "Ошибка обработки таблицы.")

        elif file_info.pipeline == PipelineType.AUDIO:
            from bot.media_engine.audio_pipeline import transcribe_audio, extract_tasks_from_transcript
            transcript = await transcribe_audio(file_data, mime_type=mime_type, diarize=True)

            if transcript:
                tasks = await extract_tasks_from_transcript(transcript)
                response = f"🎤 <b>Транскрипт:</b>\n{transcript[:2000]}\n\n{tasks}"
            else:
                response = "Не удалось распознать аудио."

        elif file_info.pipeline == PipelineType.VIDEO:
            from bot.media_engine.video_pipeline import process_video
            result = await process_video(file_data)

            if result["summary"]:
                response = f"🎬 <b>Видео:</b>\n\n{result['summary']}"
            else:
                response = "Не удалось обработать видео."

        elif file_info.pipeline == PipelineType.VISION:
            from bot.media_engine.vision import analyze_image
            analysis = await analyze_image(file_data, mime_type=mime_type)
            response = analysis or "Не удалось проанализировать изображение."

        await message.answer(response[:4000])

        if user_id:
            await _save_to_archive(
                conn, user_id, file_info.pipeline.value, filename, response,
            )

    except Exception as e:
        logger.error("document_handler_error", error=str(e), filename=filename)
        await message.answer(f"Ошибка при обработке {filename}.")
    finally:
        await conn.close()
