CREATE TABLE IF NOT EXISTS call_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    direction TEXT,
    contact_phone TEXT,
    contact_name TEXT,
    script_type TEXT,
    transcript TEXT,
    summary TEXT,
    outcome TEXT,
    duration_sec INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_call_sessions_user ON call_sessions(user_id);
