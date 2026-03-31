FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Dev: code mounted via volume ──
FROM base AS dev
CMD ["python", "-m", "bot.main"]

# ── Prod: code baked in ──
FROM base AS prod
COPY bot/ /app/bot/
COPY db/ /app/db/
CMD ["python", "-m", "bot.main"]
