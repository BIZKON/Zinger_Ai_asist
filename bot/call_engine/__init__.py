"""§12 Voice Call Engine — AI-звонки через VoximPlant.

Компоненты:
  - orchestrator: FastAPI WebSocket hub (порт 8001)
  - deepgram_stt: Real-time STT через WebSocket
  - dialog_manager: Claude диалог во время звонка
  - vox_script.js: VoxEngine скрипт для VoximPlant

Запуск voice engine:
  python -m bot.call_engine.orchestrator
"""
