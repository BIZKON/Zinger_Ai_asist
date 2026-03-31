"""File Router — MIME detection → выбор пайплайна.

Определяет тип файла и направляет в соответствующий пайплайн обработки.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger()


class PipelineType(str, Enum):
    DOCUMENT = "document"
    VISION = "vision"
    AUDIO = "audio"
    VIDEO = "video"
    TABLE = "table"
    UNSUPPORTED = "unsupported"


@dataclass
class FileInfo:
    filename: str
    mime_type: str
    file_size: int
    pipeline: PipelineType
    file_id: str = ""


# MIME → Pipeline mapping
DOCUMENT_MIMES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/rtf",
}

IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
}

AUDIO_MIMES = {
    "audio/ogg",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/aac",
    "audio/flac",
}

VIDEO_MIMES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
}

TABLE_MIMES = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/csv",
}

# File size limits (bytes)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50 MB


def detect_pipeline(filename: str, mime_type: str = "") -> PipelineType:
    """Detect which pipeline should process this file."""
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or ""

    mime_lower = mime_type.lower()

    if mime_lower in DOCUMENT_MIMES:
        return PipelineType.DOCUMENT
    if mime_lower in IMAGE_MIMES:
        return PipelineType.VISION
    if mime_lower in AUDIO_MIMES:
        return PipelineType.AUDIO
    if mime_lower in VIDEO_MIMES:
        return PipelineType.VIDEO
    if mime_lower in TABLE_MIMES:
        return PipelineType.TABLE

    # Fallback: check file extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext_map = {
        "pdf": PipelineType.DOCUMENT,
        "doc": PipelineType.DOCUMENT,
        "docx": PipelineType.DOCUMENT,
        "txt": PipelineType.DOCUMENT,
        "jpg": PipelineType.VISION,
        "jpeg": PipelineType.VISION,
        "png": PipelineType.VISION,
        "webp": PipelineType.VISION,
        "ogg": PipelineType.AUDIO,
        "mp3": PipelineType.AUDIO,
        "wav": PipelineType.AUDIO,
        "mp4": PipelineType.VIDEO,
        "avi": PipelineType.VIDEO,
        "mov": PipelineType.VIDEO,
        "xlsx": PipelineType.TABLE,
        "xls": PipelineType.TABLE,
        "csv": PipelineType.TABLE,
    }

    return ext_map.get(ext, PipelineType.UNSUPPORTED)


def route_file(
    filename: str,
    mime_type: str = "",
    file_size: int = 0,
    file_id: str = "",
) -> FileInfo:
    """Route a file to the appropriate pipeline.

    Returns FileInfo with detected pipeline type.
    """
    pipeline = detect_pipeline(filename, mime_type)

    if not mime_type:
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"

    info = FileInfo(
        filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        pipeline=pipeline,
        file_id=file_id,
    )

    logger.info(
        "file_routed",
        filename=filename,
        mime=mime_type,
        pipeline=pipeline.value,
        size=file_size,
    )

    return info
