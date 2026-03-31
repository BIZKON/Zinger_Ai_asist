CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    city TEXT DEFAULT 'Санкт-Петербург',
    timezone TEXT DEFAULT 'Europe/Moscow',
    persona TEXT DEFAULT 'sergiy',
    voice_id TEXT DEFAULT 'Maxim',
    tier TEXT DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
