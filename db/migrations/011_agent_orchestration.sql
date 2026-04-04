-- §14 Agent Orchestration Layer
-- 5 tables: agent_configs, agent_tasks, agent_goals, heartbeat_log, agent_cost_daily

-- ── Table 1: agent_configs ──

CREATE TABLE IF NOT EXISTS agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID,  -- nullable, for future multi-tenant
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'worker',  -- worker | manager | observer
    skills JSONB NOT NULL DEFAULT '[]',
    system_prompt TEXT,
    heartbeat_cron TEXT DEFAULT '0 */2 * * *',
    is_active BOOLEAN DEFAULT TRUE,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_agent_configs_user ON agent_configs(user_id);

-- ── Table 2: agent_goals ──

CREATE TABLE IF NOT EXISTS agent_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID,
    title TEXT NOT NULL,
    description TEXT,
    strategy TEXT,
    status TEXT DEFAULT 'active',  -- active | paused | completed | failed
    progress_pct SMALLINT DEFAULT 0,
    deadline TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_goals_user ON agent_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_goals_status ON agent_goals(status);

-- ── Table 3: agent_tasks ──

CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID,
    agent_id UUID REFERENCES agent_configs(id) ON DELETE CASCADE,
    goal_id UUID REFERENCES agent_goals(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',  -- pending | in_progress | waiting_approval | done | failed | cancelled
    priority TEXT DEFAULT 'medium',
    context JSONB DEFAULT '{}',
    result JSONB,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    due_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_user ON agent_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_agent ON agent_tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_goal ON agent_tasks(goal_id);

-- ── Table 4: heartbeat_log ──

CREATE TABLE IF NOT EXISTS heartbeat_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agent_configs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    duration_ms INTEGER,
    tasks_created INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    error TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_log_agent ON heartbeat_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_log_time ON heartbeat_log(triggered_at);

-- ── Table 5: agent_cost_daily ──

CREATE TABLE IF NOT EXISTS agent_cost_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agent_configs(id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    model TEXT NOT NULL,
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    call_count INTEGER DEFAULT 0,
    UNIQUE (user_id, agent_id, date, model)
);

CREATE INDEX IF NOT EXISTS idx_agent_cost_daily_user_date ON agent_cost_daily(user_id, date);

-- ── RLS ──

ALTER TABLE agent_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE heartbeat_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_cost_daily ENABLE ROW LEVEL SECURITY;

-- SELECT
CREATE POLICY agent_configs_select ON agent_configs
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_tasks_select ON agent_tasks
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_goals_select ON agent_goals
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY heartbeat_log_select ON heartbeat_log
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_cost_daily_select ON agent_cost_daily
    FOR SELECT USING (user_id::text = current_setting('app.current_user_id', TRUE));

-- INSERT
CREATE POLICY agent_configs_insert ON agent_configs
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_tasks_insert ON agent_tasks
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_goals_insert ON agent_goals
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY heartbeat_log_insert ON heartbeat_log
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_cost_daily_insert ON agent_cost_daily
    FOR INSERT WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

-- UPDATE
CREATE POLICY agent_configs_update ON agent_configs
    FOR UPDATE USING (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_tasks_update ON agent_tasks
    FOR UPDATE USING (user_id::text = current_setting('app.current_user_id', TRUE));
CREATE POLICY agent_goals_update ON agent_goals
    FOR UPDATE USING (user_id::text = current_setting('app.current_user_id', TRUE));
