-- Row-Level Security policies for all user-data tables.
-- Каждый пользователь видит только свои данные.

-- Для работы RLS приложение должно выполнять:
--   SET LOCAL app.current_user_id = '<user_uuid>';
-- перед каждым запросом.

-- ── Enable RLS ──

ALTER TABLE memory_structured ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_semantic ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_episodic ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_archive ENABLE ROW LEVEL SECURITY;

-- ── Policies: SELECT ──

CREATE POLICY memory_structured_select ON memory_structured
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY memory_semantic_select ON memory_semantic
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY memory_episodic_select ON memory_episodic
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY tasks_select ON tasks
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY contacts_select ON contacts
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY call_sessions_select ON call_sessions
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY media_archive_select ON media_archive
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

-- ── Policies: INSERT ──

CREATE POLICY memory_structured_insert ON memory_structured
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY memory_semantic_insert ON memory_semantic
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY memory_episodic_insert ON memory_episodic
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY tasks_insert ON tasks
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY contacts_insert ON contacts
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY call_sessions_insert ON call_sessions
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY media_archive_insert ON media_archive
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

-- ── Policies: UPDATE ──

CREATE POLICY tasks_update ON tasks
    FOR UPDATE USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY contacts_update ON contacts
    FOR UPDATE USING (user_id::text = current_setting('app.current_user_id', TRUE));

-- ── Policies: DELETE ──

CREATE POLICY tasks_delete ON tasks
    FOR DELETE USING (user_id::text = current_setting('app.current_user_id', TRUE));

CREATE POLICY contacts_delete ON contacts
    FOR DELETE USING (user_id::text = current_setting('app.current_user_id', TRUE));

-- ── Bypass for superuser / migrations ──
-- Суперюзер и owner БД обходят RLS автоматически.
-- Для приложения: если не задан app.current_user_id, RLS заблокирует доступ.
