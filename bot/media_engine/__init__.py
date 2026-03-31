"""§13 Media Intelligence Engine — распознавание медиа.

Пайплайны:
  - DocumentPipeline: PDF, DOCX → текст → сущности → БД
  - VisionPipeline:   JPG, PNG → OCR / Claude Vision → структура
  - AudioPipeline:    OGG, MP3 → Deepgram STT → транскрипт → задачи
  - VideoPipeline:    MP4 → FFmpeg + STT → саммари
  - TablePipeline:    Excel, CSV → Pandas → нормализация
"""
