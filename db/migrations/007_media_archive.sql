CREATE TABLE IF NOT EXISTS media_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    file_type TEXT,
    original_filename TEXT,
    storage_path TEXT,
    extracted_text TEXT,
    entities JSONB,
    embedding vector(1536),
    one_c_synced BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_archive_user ON media_archive(user_id);
CREATE INDEX IF NOT EXISTS idx_media_archive_embedding
    ON media_archive USING hnsw (embedding vector_cosine_ops);
