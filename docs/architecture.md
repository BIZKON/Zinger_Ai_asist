# Архитектура PersonalAI Sergiy

## Компоненты

```
Telegram ←→ aiogram Bot ←→ Services ←→ External APIs
                ↕                          ↕
           PostgreSQL + pgvector      Claude / Gemini
                ↕                     ElevenLabs / Deepgram
              Redis                   VoximPlant
                                      Yandex (Погода, Карты)
                                      1С OData
                                      Perplexity
```

## Стек

- **Backend:** Python 3.12, aiogram 3.x, asyncpg, SQLAlchemy async
- **Database:** PostgreSQL 16 + pgvector (HNSW indexes)
- **Cache:** Redis 7
- **LLM:** Claude Sonnet (основной), Gemini Flash (интенты), OpenRouter (fallback)
- **Voice:** ElevenLabs V3 (TTS), Deepgram Nova-2 (STT)
- **Telephony:** VoximPlant
- **Infrastructure:** Docker, Timeweb VPS, Cloudflare Tunnel, GitHub Actions

## Деплой

GitHub push → Actions lint → SSH deploy → docker compose up
