# Развёртывание PersonalAI Sergiy на Timeweb Cloud VPS

Пошаговая инструкция первого запуска бота в **polling-режиме** (без домена и
SSL). PostgreSQL и Redis работают в Docker на том же VPS.

---

## Что понадобится

- VPS на Timeweb Cloud (Ubuntu 22.04+, минимум 1 vCPU / 2 ГБ RAM)
- SSH-доступ к VPS под `root` или пользователем с `sudo`
- Токен Telegram-бота (@BotFather → `/newbot`)
- **Ключ YandexGPT** (см. раздел «Получение ключа YandexGPT» ниже) —
  Anthropic/OpenAI блокируют запросы из РФ, поэтому для VPS в
  Санкт-Петербурге используем YandexGPT
- Ваш Telegram ID (можно получить у @userinfobot)

---

## Получение ключа YandexGPT

1. Зайдите в [Yandex Cloud Console](https://console.yandex.cloud/)
2. Создайте **облако** и **каталог** (folder), если их нет
3. Скопируйте **Folder ID** (строка вида `b1g...`) — он нужен для `.env`
4. Откройте раздел «Сервисные аккаунты» → создайте аккаунт с ролью
   `ai.languageModels.user`
5. На странице созданного аккаунта: «Создать новый ключ» → **API-ключ**
6. Скопируйте значение API-ключа (показывается один раз!) → в `.env` как
   `YANDEX_GPT_API_KEY`
7. Убедитесь, что в каталоге подключён сервис **Yandex Foundation Models**
   (Биллинг → привязка платёжного аккаунта)

---

## Фаза 1. Первичная настройка VPS

Подключитесь к серверу по SSH и выполните скрипт установки:

```bash
ssh root@<IP_вашего_VPS>

curl -fsSL https://raw.githubusercontent.com/bizkon/zinger_ai_asist/claude/setup-personalai-sergiy-8pw8q/infrastructure/timeweb_setup.sh | bash
```

Скрипт установит:

- Docker Engine + `docker-compose-plugin`
- Пользователя `personalai` (в группе `docker`)
- UFW firewall (разрешены только SSH / 80 / 443)
- Swap-файл на 2 ГБ
- `certbot` (понадобится позже, если подключите домен)

---

## Фаза 2. Клонирование репозитория

```bash
sudo -iu personalai
git clone -b claude/setup-personalai-sergiy-8pw8q \
    https://github.com/bizkon/zinger_ai_asist.git /opt/personalai
cd /opt/personalai
```

---

## Фаза 3. Конфигурация `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

### Обязательные переменные

| Переменная | Где взять | Пример |
|---|---|---|
| `BOT_TOKEN` | @BotFather → `/newbot` | `123456:ABC-DEF...` |
| `POSTGRES_PASSWORD` | Сгенерируйте сами | 32+ символов |
| `REDIS_PASSWORD` | Сгенерируйте сами | 32+ символов |
| `YANDEX_GPT_API_KEY` | Yandex Cloud (см. выше) | `AQVN...` |
| `YANDEX_GPT_FOLDER_ID` | Yandex Cloud Console | `b1g...` |
| `ADMIN_USER_IDS` | @userinfobot | `123456789` |
| `ENVIRONMENT` | вручную | `production` |

### Важно оставить пустым

```
WEBHOOK_URL=
```

Пустой `WEBHOOK_URL` включает polling-режим (см. `bot/main.py`).

### Генерация надёжных паролей

```bash
openssl rand -base64 32
```

### Опциональные ключи (можно добавить позже)

- `ANTHROPIC_API_KEY` — Claude (работает только если VPS вне РФ)
- `OPENAI_API_KEY` — GPT-4o (работает только если VPS вне РФ)
- `GEMINI_API_KEY` — бесплатные простые интенты (может быть недоступен из РФ)
- `ELEVENLABS_API_KEY`, `DEEPGRAM_API_KEY` — голосовые функции
- `YANDEX_WEATHER_KEY`, `YANDEX_MAPS_KEY` — погода и пробки
- `ONE_C_BASE_URL/USERNAME/PASSWORD` — интеграция с 1С
- `SENTRY_DSN` — мониторинг ошибок
- `YUKASSA_SHOP_ID/SECRET_KEY` — платежи

---

## Фаза 4. Сборка и запуск контейнеров

```bash
cd /opt/personalai
docker compose -f docker-compose.polling.yml up -d --build
```

Проверка состояния:

```bash
docker compose -f docker-compose.polling.yml ps
```

Ожидаемый вывод — три контейнера в статусе `Up (healthy)`:

```
NAME                    STATUS
personalai-bot-1        Up 30 seconds
personalai-db-1         Up 30 seconds (healthy)
personalai-redis-1      Up 30 seconds (healthy)
```

---

## Фаза 5. Применение миграций БД

Применяем все 11 SQL-миграций (`001_extensions` … `011_agent_orchestration`):

```bash
docker compose -f docker-compose.polling.yml exec bot python -m bot.migrate
```

Проверка списка таблиц:

```bash
docker compose -f docker-compose.polling.yml exec db \
    psql -U personalai -d personalai -c "\dt"
```

Должны быть созданы 15+ таблиц:
`users`, `memory_structured`, `memory_semantic`, `memory_episodic`,
`tasks`, `events`, `contacts`, `call_sessions`, `media_archive`,
`agent_configs`, `agent_tasks`, `agent_goals`, `heartbeat_log`,
`agent_cost_daily`, `_migrations`, и др.

---

## Фаза 6. Smoke-тест

### Логи бота

```bash
docker compose -f docker-compose.polling.yml logs -f bot
```

Ожидаем записи:
- `starting_bot environment=production`
- `heartbeat_started`
- Отсутствие `ERROR` / `Traceback`

### Проверка в Telegram

1. Напишите боту `/start` — должен ответить приветствием «Сергия».
2. `/agents` → «У вас нет агентов» (нормально на первом запуске).
3. `/agent_cost` → сводка за сегодня ($0.0000).
4. `/tasks` → пустой список.

---

## Фаза 7. Эксплуатация

### Полезные команды

```bash
# Посмотреть логи
docker compose -f docker-compose.polling.yml logs -f bot

# Перезапустить бота после обновления .env
docker compose -f docker-compose.polling.yml restart bot

# Применить обновление из git
cd /opt/personalai
git pull
docker compose -f docker-compose.polling.yml up -d --build
docker compose -f docker-compose.polling.yml exec bot python -m bot.migrate

# Открыть psql
docker compose -f docker-compose.polling.yml exec db \
    psql -U personalai -d personalai

# Redis CLI (пароль подставится из .env)
docker compose -f docker-compose.polling.yml exec redis \
    redis-cli -a "$REDIS_PASSWORD"

# Остановить всё (данные в volumes сохранятся)
docker compose -f docker-compose.polling.yml down
```

### Авто-перезапуск после ребута

- `restart: always` прописан в compose — контейнеры поднимутся автоматически
- Убедитесь, что Docker стартует при загрузке системы:
  ```bash
  sudo systemctl enable docker
  ```

### Ротация логов

Логи Docker ротируются автоматически (10 МБ × 3 файла на контейнер, настроено
в `docker-compose.polling.yml`).

---

## Решение проблем

### Бот не отвечает

1. Проверить логи: `docker compose -f docker-compose.polling.yml logs bot`
2. Проверить `BOT_TOKEN` в `.env` (не должно быть лишних пробелов/кавычек)
3. Убедиться, что нет активного webhook:
   ```bash
   curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
   ```
   Если URL не пустой — удалить его через `deleteWebhook`.

### Ошибки LLM

- `yandex_gpt_error` → проверить `YANDEX_GPT_API_KEY` и `YANDEX_GPT_FOLDER_ID`,
  баланс в Yandex Cloud, роль `ai.languageModels.user` у сервисного аккаунта
- `anthropic_error` → Anthropic блокирует РФ-IP; используйте YandexGPT
- `openai_error` → OpenAI блокирует РФ-IP; используйте YandexGPT

### Контейнер БД не стартует

- Убедитесь, что `POSTGRES_PASSWORD` задан в `.env`
- Проверьте место на диске: `df -h`

### Миграция упала

- Логи: `docker compose -f docker-compose.polling.yml exec bot python -m bot.migrate`
- Посмотреть, какие миграции уже применены:
  ```bash
  docker compose -f docker-compose.polling.yml exec db \
      psql -U personalai -d personalai -c "SELECT name FROM _migrations;"
  ```

---

## Что дальше (вне этого гайда)

- Купить домен → привязать к IP VPS → получить SSL через `certbot` →
  переключиться на webhook-режим (`docker-compose.prod.yml` с nginx)
- Добавить API-ключи для голоса/медиа/1С/платежей
- Настроить Cloudflare Tunnel для интеграции с 1С on-premise
- Создать первого агента в `agent_configs` для Сергея Доронина
- Подключить Sentry для мониторинга (`SENTRY_DSN`)
- Настроить GitHub Secrets (`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`) для
  авто-деплоя через `.github/workflows/deploy.yml`
