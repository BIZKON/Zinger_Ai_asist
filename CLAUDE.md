# PersonalAI Sergiy — Рабочий план для Claude Code

> Этот файл — главный контекст проекта. Читай его полностью перед любой задачей.
> Обновляй раздел «Текущий статус» после каждой завершённой фазы.

---

## 🎯 Что строим

**PersonalAI Sergiy** — персональный ИИ-ассистент для предпринимателей в Telegram.
Первый клиент: Сергей Доронин, ООО «Зингер Логистика» (грузоперевозки, Санкт-Петербург).

Продукт = Telegram-бот + Mini App + голосовые звонки + распознавание медиа + 1С интеграция.
Характер: ироничный персонаж «Сергий» (голос ElevenLabs Maxim, саркастичный, умный, по делу).

**Документы PRD:** `docs/PRD_v6.md` и `docs/PRD_v7.md` — читай перед реализацией каждой фичи.

---

## 📁 Структура репозитория

```
personalai-sergiy/
│
├── CLAUDE.md                    ← этот файл, главный контекст
├── .env.example                 ← шаблон переменных (без секретов!)
├── .gitignore
├── docker-compose.yml           ← локальная разработка
├── docker-compose.prod.yml      ← продакшн на Timeweb
├── Makefile                     ← команды: make dev, make deploy, make migrate
│
├── docs/
│   ├── PRD_v6.md               ← PRD версия 6 (ядро платформы)
│   ├── PRD_v7.md               ← PRD версия 7 (§12 звонки, §13 медиа)
│   ├── architecture.md         ← схемы и решения
│   └── 1c_odata.md             ← инструкция по OData
│
├── bot/                         ← aiogram 3.x бот (Python)
│   ├── __init__.py
│   ├── main.py                  ← точка входа, webhook/polling
│   ├── config.py                ← настройки через pydantic-settings
│   ├── database.py              ← подключение к PostgreSQL + pgvector
│   │
│   ├── handlers/                ← обработчики сообщений
│   │   ├── __init__.py
│   │   ├── start.py             ← /start, онбординг
│   │   ├── voice.py             ← голосовые сообщения → Deepgram STT
│   │   ├── media.py             ← фото, документы, аудио → §13
│   │   ├── tasks.py             ← задачи CRUD
│   │   ├── schedule.py          ← расписание, события
│   │   ├── contacts.py          ← контакты, SMS
│   │   ├── digest.py            ← утренний/вечерний дайджест
│   │   └── callbacks.py         ← inline-кнопки
│   │
│   ├── services/                ← бизнес-логика и внешние API
│   │   ├── __init__.py
│   │   ├── llm.py               ← Claude API + каскадный роутинг
│   │   ├── memory.py            ← 6-слойная память (pgvector)
│   │   ├── persona.py           ← система персонажей + Mood Engine
│   │   ├── weather.py           ← Яндекс.Погода API
│   │   ├── traffic.py           ← Яндекс.Карты (пробки)
│   │   ├── research.py          ← Perplexity Sonar API
│   │   ├── one_c.py             ← 1С OData API
│   │   ├── voice_tts.py         ← ElevenLabs V3 (голосовые ответы)
│   │   └── notifications.py     ← проактивные алерты (42 сценария)
│   │
│   ├── call_engine/             ← §12 Voice Call Engine
│   │   ├── __init__.py
│   │   ├── orchestrator.py      ← FastAPI WebSocket hub
│   │   ├── vox_script.js        ← VoxEngine скрипт для VoximPlant
│   │   ├── deepgram_stt.py      ← STT для звонков
│   │   └── dialog_manager.py    ← Claude диалог во время звонка
│   │
│   ├── media_engine/            ← §13 Media Intelligence Engine
│   │   ├── __init__.py
│   │   ├── router.py            ← File Router (MIME detection)
│   │   ├── ocr.py               ← Yandex Vision OCR
│   │   ├── vision.py            ← Claude Vision (фото)
│   │   ├── audio_pipeline.py    ← Deepgram STT для аудиофайлов
│   │   ├── video_pipeline.py    ← FFmpeg + Whisper
│   │   ├── doc_parser.py        ← LlamaParse / PDF
│   │   └── table_parser.py      ← Pandas + openpyxl
│   │
│   └── models/                  ← Pydantic модели данных
│       ├── __init__.py
│       ├── user.py
│       ├── memory.py
│       ├── task.py
│       └── call_session.py
│
├── db/
│   ├── migrations/              ← SQL миграции (по порядку)
│   │   ├── 001_extensions.sql
│   │   ├── 002_users.sql
│   │   ├── 003_memory_layers.sql
│   │   ├── 004_tasks_events.sql
│   │   ├── 005_contacts.sql
│   │   ├── 006_call_sessions.sql
│   │   └── 007_media_archive.sql
│   └── seed.py                  ← тестовые данные для разработки
│
├── miniapp/                     ← Telegram Mini App (React)
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── CharacterShop.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   └── MediaArchive.tsx
│   │   └── components/
│   └── dist/
│
├── infrastructure/
│   ├── nginx.conf               ← reverse proxy + SSL
│   ├── timeweb_setup.sh         ← скрипт первичной настройки VPS
│   └── cloudflare_tunnel.yml    ← туннель к 1С on-premise
│
└── .github/
    └── workflows/
        └── deploy.yml           ← GitHub Actions → Timeweb VPS
```

---

## 🔑 Переменные окружения

Все переменные описаны в `.env.example`. Никогда не коммить `.env` с секретами.

---

## 🗄️ Схема базы данных

Определена в `db/migrations/`. Ключевые таблицы:
- `users` — UUID PK, telegram_id, persona, tier
- `memory_structured` — факты о пользователе (category/key/value)
- `memory_semantic` — векторные embeddings (pgvector, HNSW)
- `memory_episodic` — саммари разговоров
- `tasks` — задачи с приоритетом и статусом
- `call_sessions` — сессии звонков (§12)
- `media_archive` — архив медиа с OCR и embeddings (§13)

---

## 📋 ФАЗЫ РАЗРАБОТКИ

| Фаза | Описание | Статус |
|------|----------|--------|
| 0 | Инфраструктура (Docker, CI/CD, структура) | ✅ Готово |
| 1 | Ядро бота (характер, память, команды) | ✅ Готово |
| 2 | 1С интеграция (OData, Cloudflare Tunnel) | ✅ Готово |
| 3 | Голосовые звонки (VoximPlant, ElevenLabs) | ⏳ |
| 4 | Media Intelligence Engine | ⏳ |
| 5 | Research Engine + Проактивные сценарии | ⏳ |
| 6 | Mini App (React) | ⏳ |
| 7 | Продакшн-хардение (security, оплата) | ⏳ |

---

## 🧠 Правила для Claude Code

1. **Читай PRD** перед реализацией каждой фичи — `docs/PRD_v6.md` и `docs/PRD_v7.md`
2. **Пиши тесты** для каждого сервиса в `tests/`
3. **Async везде** — aiogram 3.x требует async, используй `asyncpg`, не `psycopg2`
4. **Никаких секретов в коде** — только `os.getenv()` или `settings.field`
5. **Логируй** каждый внешний API вызов: время, статус, cost в рублях
6. **Обрабатывай ошибки API** — все внешние вызовы в try/except с fallback
7. **Каскадный LLM** — не используй Claude для простых интентов, Gemini Flash бесплатен
8. **pgvector индекс HNSW** — не IVFFlat, лучше для нашего масштаба
9. **RLS обязательно** — каждая новая таблица → политика изоляции по user_id
10. **Обновляй этот файл** — после завершения каждой фазы обновляй статус
