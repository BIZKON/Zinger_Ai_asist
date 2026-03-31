-- Таблица платежей (ЮKassa)

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    yukassa_payment_id TEXT UNIQUE,
    amount NUMERIC(10, 2) NOT NULL,
    currency TEXT DEFAULT 'RUB',
    status TEXT DEFAULT 'pending',
    tier TEXT,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_yukassa ON payments(yukassa_payment_id);

-- Тарифные лимиты
CREATE TABLE IF NOT EXISTS tier_limits (
    tier TEXT PRIMARY KEY,
    messages_per_day INTEGER DEFAULT 50,
    calls_per_month INTEGER DEFAULT 0,
    files_per_month INTEGER DEFAULT 10,
    research_per_month INTEGER DEFAULT 5,
    price_rub NUMERIC(10, 2) DEFAULT 0
);

-- Заполняем тарифы
INSERT INTO tier_limits (tier, messages_per_day, calls_per_month, files_per_month, research_per_month, price_rub)
VALUES
    ('free',     50,  0,  10,  5,    0),
    ('starter', 200,  5,  50, 20,  490),
    ('pro',     999, 30, 200, 50, 1490),
    ('business',999, 99, 999, 99, 4990)
ON CONFLICT (tier) DO NOTHING;
