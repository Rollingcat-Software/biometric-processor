-- Database initialization for Biometric Processor
-- Requires PostgreSQL 14+ with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Face embeddings table
CREATE TABLE IF NOT EXISTS face_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255),
    embedding vector(512) NOT NULL,
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0 AND quality_score <= 100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Unique constraint per user per tenant
    CONSTRAINT unique_user_tenant UNIQUE (user_id, tenant_id)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_embeddings_user_id ON face_embeddings(user_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_tenant_id ON face_embeddings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON face_embeddings(created_at);

-- Vector similarity index (IVFFlat for approximate nearest neighbor)
-- This index significantly speeds up similarity searches
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON face_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- API keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    key_prefix VARCHAR(8) NOT NULL,         -- First 8 chars for identification
    tenant_id VARCHAR(255) NOT NULL,
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    tier VARCHAR(50) DEFAULT 'standard',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- Indexes for API keys
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_id ON api_keys(tenant_id);

-- Rate limit entries table (optional, for persistent rate limiting)
CREATE TABLE IF NOT EXISTS rate_limit_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) NOT NULL UNIQUE,
    count INTEGER DEFAULT 0,
    window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tier VARCHAR(50) DEFAULT 'standard',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for rate limit lookups
CREATE INDEX IF NOT EXISTS idx_rate_limit_key ON rate_limit_entries(key);

-- Webhook events table (for audit trail)
CREATE TABLE IF NOT EXISTS webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    url VARCHAR(2048) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_code INTEGER,
    response_body TEXT
);

-- Index for webhook event queries
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status);
CREATE INDEX IF NOT EXISTS idx_webhook_events_created_at ON webhook_events(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for face_embeddings
DROP TRIGGER IF EXISTS update_face_embeddings_updated_at ON face_embeddings;
CREATE TRIGGER update_face_embeddings_updated_at
    BEFORE UPDATE ON face_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for rate_limit_entries
DROP TRIGGER IF EXISTS update_rate_limit_entries_updated_at ON rate_limit_entries;
CREATE TRIGGER update_rate_limit_entries_updated_at
    BEFORE UPDATE ON rate_limit_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO biometric_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO biometric_user;

-- Verify setup
DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete';
    RAISE NOTICE 'Tables created: face_embeddings, api_keys, rate_limit_entries, webhook_events';
    RAISE NOTICE 'Vector dimension: 512';
    RAISE NOTICE 'Index type: IVFFlat with cosine distance';
END $$;
