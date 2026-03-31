"""PDF / DOCX — парсинг документов.

Извлечение текста из PDF и DOCX файлов.
Для сложных PDF с таблицами — fallback на Claude Vision.
"""

from __future__ import annotations

import io
import time

import structlog

logger = structlog.get_logger()


async def parse_pdf(pdf_data: bytes) -> str | None:
    """Extract text from PDF file.

    Uses PyPDF2 for simple text extraction.
    Falls back to OCR for scanned PDFs.
    """
    start = time.monotonic()

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_data))
        pages = []

        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())

        elapsed = time.monotonic() - start
        full_text = "\n\n".join(pages)

        logger.info(
            "pdf_parsed",
            pages=len(reader.pages),
            text_length=len(full_text),
            elapsed_sec=round(elapsed, 2),
        )

        if not full_text:
            logger.info("pdf_no_text_fallback_ocr")
            return None  # Caller should try OCR

        return full_text

    except ImportError:
        logger.warning("pypdf_not_installed")
        return None
    except Exception as e:
        logger.error("pdf_parse_error", error=str(e))
        return None


async def parse_docx(docx_data: bytes) -> str | None:
    """Extract text from DOCX file."""
    start = time.monotonic()

    try:
        from docx import Document

        doc = Document(io.BytesIO(docx_data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        elapsed = time.monotonic() - start
        logger.info(
            "docx_parsed",
            paragraphs=len(paragraphs),
            text_length=len(full_text),
            elapsed_sec=round(elapsed, 2),
        )
        return full_text if full_text else None

    except ImportError:
        logger.warning("python_docx_not_installed")
        return None
    except Exception as e:
        logger.error("docx_parse_error", error=str(e))
        return None


async def parse_document(doc_data: bytes, filename: str) -> str | None:
    """Parse document based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return await parse_pdf(doc_data)
    elif ext in ("docx", "doc"):
        return await parse_docx(doc_data)
    elif ext == "txt":
        try:
            return doc_data.decode("utf-8")
        except UnicodeDecodeError:
            return doc_data.decode("cp1251", errors="replace")
    else:
        logger.warning("unsupported_doc_format", ext=ext)
        return None
