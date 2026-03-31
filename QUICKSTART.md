# Быстрый старт PersonalAI Sergiy

## Что нужно

- **Docker Desktop** — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
- **BOT_TOKEN** — создай бота у [@BotFather](https://t.me/BotFather) в Telegram
- **ANTHROPIC_API_KEY** — зарегистрируйся на [console.anthropic.com](https://console.anthropic.com)

## Запуск за 3 шага

```bash
# 1. Клонируй
git clone https://github.com/BIZKON/Zinger_Ai_asist.git
cd Zinger_Ai_asist

# 2. Настрой
cp .env.dev.example .env
# Открой .env и впиши BOT_TOKEN и ANTHROPIC_API_KEY

# 3. Запусти
docker compose -f docker-compose.dev.yml up --build
```

## Проверка

1. **Бот** — открой Telegram, найди своего бота, напиши `/start`
2. **Mini App** — в отдельном терминале:
   ```bash
   cd miniapp
   npm install
   npm run dev
   ```
   Откроется [http://localhost:5173/miniapp/](http://localhost:5173/miniapp/)

## Применить миграции БД

```bash
docker compose -f docker-compose.dev.yml exec bot python -m bot.migrate
```

## Что работает без дополнительных ключей

| Функция | Работает? | Нужен ключ |
|---------|-----------|------------|
| Чат с ИИ (Сергий) | ✅ | ANTHROPIC_API_KEY |
| Онбординг /start | ✅ | — |
| Задачи /tasks | ✅ | — |
| Голосовые сообщения | ❌ | DEEPGRAM_API_KEY |
| Погода в дайджесте | ❌ | YANDEX_WEATHER_KEY |
| Поиск /search | ❌ | PERPLEXITY_API_KEY |
| 1С интеграция | ❌ | ONE_C_BASE_URL |

## Остановка

```bash
docker compose -f docker-compose.dev.yml down
```
