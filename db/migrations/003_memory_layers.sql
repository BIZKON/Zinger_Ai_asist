-- Структурированная память (факты о пользователе)
CREATE TABLE IF NOT EXISTS memory_structured (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    category TEXT,
    key TEXT,
    value TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_structured_user ON memory_structured(user_id);

-- Семантическая память (векторные embeddings)
CREATE TABLE IF NOT EXISTS memory_semantic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT,
    embedding vector(1536),
    source TEXT DEFAULT 'dialog',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_semantic_user ON memory_semantic(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_semantic_embedding
    ON memory_semantic USING hnsw (embedding vector_cosine_ops);

-- Эпизодическая память (саммари разговоров)
CREATE TABLE IF NOT EXISTS memory_episodic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    summary TEXT,
    embedding vector(1536),
    relevance_score FLOAT DEFAULT 1.0,
    session_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_episodic_user ON memory_episodic(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_episodic_embedding
    ON memory_episodic USING hnsw (embedding vector_cosine_ops);
