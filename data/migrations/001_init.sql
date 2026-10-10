-- ═══════════════════════════════════════════════════════════
-- OMNIVERSO — Initial Database Schema
-- Migration 001: Core tables
-- ═══════════════════════════════════════════════════════════

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Users ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('admin', 'user', 'api', 'bot')),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ─── API Keys ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash        VARCHAR(255) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    prefix          VARCHAR(10) NOT NULL,
    scopes          TEXT[] DEFAULT ARRAY['read'],
    rate_limit      INTEGER DEFAULT 120,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- ─── Agents ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) UNIQUE NOT NULL,
    description     TEXT,
    agent_type      VARCHAR(50) NOT NULL DEFAULT 'general'
                    CHECK (agent_type IN ('general', 'research', 'code', 'trading',
                                          'content', 'data', 'security', 'custom')),
    system_prompt   TEXT,
    model_config    JSONB DEFAULT '{}',
    tools           TEXT[] DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    metadata        JSONB DEFAULT '{}',
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agents_type ON agents(agent_type);
CREATE INDEX idx_agents_active ON agents(is_active);

-- ─── Tasks ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id        UUID REFERENCES agents(id),
    user_id         UUID REFERENCES users(id),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'queued', 'running', 'completed',
                                      'failed', 'cancelled')),
    priority        INTEGER NOT NULL DEFAULT 5
                    CHECK (priority BETWEEN 1 AND 10),
    input_data      JSONB DEFAULT '{}',
    output_data     JSONB DEFAULT '{}',
    error_message   TEXT,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_agent ON tasks(agent_id);
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_priority ON tasks(priority DESC, created_at ASC);

-- ─── Conversations ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id        UUID REFERENCES agents(id),
    title           VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_user ON conversations(user_id);

-- ─── Messages ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content         TEXT NOT NULL,
    model_used      VARCHAR(100),
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    cost_usd        DECIMAL(10, 6),
    tool_calls      JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- ─── Model Usage Tracking ────────────────────────────────
CREATE TABLE IF NOT EXISTS model_usage (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id),
    provider        VARCHAR(50) NOT NULL,
    model           VARCHAR(100) NOT NULL,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    cost_usd        DECIMAL(10, 6) NOT NULL DEFAULT 0,
    latency_ms      INTEGER,
    status          VARCHAR(20) DEFAULT 'success',
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_usage_user ON model_usage(user_id, created_at);
CREATE INDEX idx_model_usage_provider ON model_usage(provider, created_at);

-- ─── Revenue Tracking ───────────────────────────────────
CREATE TABLE IF NOT EXISTS revenue_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          VARCHAR(50) NOT NULL
                    CHECK (source IN ('api', 'subscription', 'bot', 'trading',
                                      'consulting', 'other')),
    amount_usd      DECIMAL(12, 4) NOT NULL,
    currency        VARCHAR(10) DEFAULT 'USD',
    description     TEXT,
    user_id         UUID REFERENCES users(id),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_revenue_source ON revenue_events(source, created_at);
CREATE INDEX idx_revenue_date ON revenue_events(created_at);

-- ─── Updated At Trigger ─────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_agents_updated
    BEFORE UPDATE ON agents FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_tasks_updated
    BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_conversations_updated
    BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─── Seed: Admin User ────────────────────────────────────
INSERT INTO users (email, password_hash, display_name, role)
VALUES (
    'admin@omniverso.digital',
    crypt('omniverso_admin_2024', gen_salt('bf')),
    'Omniverso Admin',
    'admin'
) ON CONFLICT (email) DO NOTHING;

-- ─── Seed: Default Agents ────────────────────────────────
INSERT INTO agents (name, description, agent_type, system_prompt, tools) VALUES
    ('Research Agent', 'General-purpose research and analysis agent', 'research',
     'You are a research agent for the Omniverso ecosystem. Analyze data, summarize findings, and provide actionable insights.',
     ARRAY['web_search', 'document_reader', 'data_analyzer']),
    ('Code Agent', 'Code generation, review, and debugging agent', 'code',
     'You are a code agent. Write clean, documented, production-ready code. Always include tests.',
     ARRAY['code_generator', 'code_reviewer', 'test_writer']),
    ('Trading Agent', 'Market analysis and trading signal agent', 'trading',
     'You are a trading agent. Analyze market data, identify patterns, and generate trading signals with risk assessments.',
     ARRAY['market_data', 'technical_analysis', 'risk_calculator']),
    ('Content Agent', 'Content creation and SEO optimization agent', 'content',
     'You are a content agent. Create engaging, SEO-optimized content for multiple platforms.',
     ARRAY['content_writer', 'seo_analyzer', 'social_publisher'])
ON CONFLICT (name) DO NOTHING;
