"""Tests for media engine file router."""

from bot.media_engine.router import PipelineType, detect_pipeline, route_file


def test_detect_pdf():
    assert detect_pipeline("doc.pdf", "application/pdf") == PipelineType.DOCUMENT


def test_detect_docx():
    assert detect_pipeline("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document") == PipelineType.DOCUMENT


def test_detect_jpeg():
    assert detect_pipeline("photo.jpg", "image/jpeg") == PipelineType.VISION


def test_detect_png():
    assert detect_pipeline("scan.png", "image/png") == PipelineType.VISION


def test_detect_audio():
    assert detect_pipeline("voice.ogg", "audio/ogg") == PipelineType.AUDIO
    assert detect_pipeline("song.mp3", "audio/mpeg") == PipelineType.AUDIO


def test_detect_video():
    assert detect_pipeline("meeting.mp4", "video/mp4") == PipelineType.VIDEO


def test_detect_excel():
    assert detect_pipeline("data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == PipelineType.TABLE


def test_detect_csv():
    assert detect_pipeline("report.csv", "text/csv") == PipelineType.TABLE


def test_detect_by_extension():
    assert detect_pipeline("file.pdf") == PipelineType.DOCUMENT
    assert detect_pipeline("file.jpg") == PipelineType.VISION
    assert detect_pipeline("file.mp4") == PipelineType.VIDEO
    assert detect_pipeline("file.xlsx") == PipelineType.TABLE


def test_detect_unsupported():
    assert detect_pipeline("file.xyz", "application/octet-stream") == PipelineType.UNSUPPORTED


def test_route_file():
    info = route_file("invoice.pdf", "application/pdf", 1024, "file123")
    assert info.pipeline == PipelineType.DOCUMENT
    assert info.filename == "invoice.pdf"
    assert info.file_size == 1024
    assert info.file_id == "file123"
