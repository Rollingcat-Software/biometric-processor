-- PostgreSQL Database Initialization Script
-- This script sets up the database for the Biometric Processor API
-- with proper security, performance optimizations, and pgvector extension

-- ============================================================================
-- 1. Database Configuration
-- ============================================================================

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search optimization

-- Performance tuning
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- ============================================================================
-- 2. Security Configuration
-- ============================================================================

-- Revoke public access
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO biometric_user;

-- Create read-only role for analytics
CREATE ROLE biometric_readonly;
GRANT CONNECT ON DATABASE biometric_db TO biometric_readonly;
GRANT USAGE ON SCHEMA public TO biometric_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO biometric_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO biometric_readonly;

-- ============================================================================
-- 3. Custom Types and Enums
-- ============================================================================

-- Session status for proctoring
CREATE TYPE session_status AS ENUM (
    'CREATED',
    'INITIALIZING',
    'ACTIVE',
    'PAUSED',
    'FLAGGED',
    'COMPLETED',
    'TERMINATED',
    'EXPIRED'
);

-- Incident types for proctoring
CREATE TYPE incident_type AS ENUM (
    'FACE_NOT_DETECTED',
    'MULTIPLE_FACES',
    'GAZE_AWAY',
    'OBJECT_DETECTED',
    'AUDIO_ANOMALY',
    'TAB_SWITCH',
    'VERIFICATION_FAILED',
    'DEEPFAKE_SUSPECTED',
    'HEAD_MOVEMENT',
    'PHONE_DETECTED',
    'OTHER'
);

-- Incident severity levels
CREATE TYPE incident_severity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

-- Review actions for incidents
CREATE TYPE review_action AS ENUM (
    'PENDING',
    'DISMISSED',
    'CONFIRMED',
    'ESCALATED'
);

-- API key tiers
CREATE TYPE api_key_tier AS ENUM (
    'FREE',
    'BASIC',
    'PREMIUM',
    'ENTERPRISE'
);

-- ============================================================================
-- 4. Core Tables
-- ============================================================================

-- Face embeddings table with vector support
CREATE TABLE IF NOT EXISTS face_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255),
    embedding vector(512) NOT NULL,  -- 512-dimensional vector for Facenet512
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0 AND quality_score <= 100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Composite unique constraint for user_id + tenant_id
    CONSTRAINT unique_user_tenant UNIQUE (user_id, tenant_id)
);

-- Create indexes for face_embeddings
CREATE INDEX idx_face_embeddings_user_id ON face_embeddings(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_face_embeddings_tenant_id ON face_embeddings(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_face_embeddings_created_at ON face_embeddings(created_at DESC);
CREATE INDEX idx_face_embeddings_quality_score ON face_embeddings(quality_score DESC);

-- Vector similarity index using IVFFlat for fast approximate search
-- L2 distance for cosine similarity (embeddings are normalized)
CREATE INDEX idx_face_embeddings_vector ON face_embeddings
    USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100)
    WHERE deleted_at IS NULL;

-- Voice enrollments table with vector support
-- Stores speaker embeddings (Resemblyzer GE2E 256-dim): INDIVIDUAL rows + CENTROID per user
CREATE TABLE IF NOT EXISTS voice_enrollments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255),
    embedding vector(256) NOT NULL,
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    enrollment_type VARCHAR(50) NOT NULL CHECK (enrollment_type IN ('INDIVIDUAL', 'CENTROID')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Ensure only one CENTROID per user per tenant
CREATE UNIQUE INDEX IF NOT EXISTS uq_voice_centroid
    ON voice_enrollments(user_id, COALESCE(tenant_id, ''))
    WHERE enrollment_type = 'CENTROID' AND deleted_at IS NULL;

-- Fast lookup by user
CREATE INDEX IF NOT EXISTS idx_voice_enrollments_user_id
    ON voice_enrollments(user_id)
    WHERE deleted_at IS NULL;

-- Fast lookup by type (for centroid queries)
CREATE INDEX IF NOT EXISTS idx_voice_enrollments_type
    ON voice_enrollments(enrollment_type);

-- pgvector IVFFlat index for 1:N search (256-dim, <1M rows)
CREATE INDEX IF NOT EXISTS idx_voice_embeddings_ivfflat
    ON voice_enrollments USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- 5. Proctoring Tables
-- ============================================================================

-- Proctoring sessions
CREATE TABLE IF NOT EXISTS proctor_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    exam_id VARCHAR(255),
    tenant_id VARCHAR(255),
    status session_status NOT NULL DEFAULT 'CREATED',
    risk_score FLOAT NOT NULL DEFAULT 0.0 CHECK (risk_score >= 0 AND risk_score <= 100),
    reference_embedding vector(512),
    config JSONB DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    termination_reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for proctor_sessions
CREATE INDEX idx_proctor_sessions_session_id ON proctor_sessions(session_id);
CREATE INDEX idx_proctor_sessions_user_id ON proctor_sessions(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_proctor_sessions_status ON proctor_sessions(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_proctor_sessions_created_at ON proctor_sessions(created_at DESC);

-- Proctoring incidents
CREATE TABLE IF NOT EXISTS proctor_incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    incident_type incident_type NOT NULL,
    severity incident_severity NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    review_status review_action NOT NULL DEFAULT 'PENDING',
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for proctor_incidents
CREATE INDEX idx_proctor_incidents_session_id ON proctor_incidents(session_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_proctor_incidents_type ON proctor_incidents(incident_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_proctor_incidents_severity ON proctor_incidents(severity) WHERE deleted_at IS NULL;
CREATE INDEX idx_proctor_incidents_review_status ON proctor_incidents(review_status) WHERE deleted_at IS NULL;
CREATE INDEX idx_proctor_incidents_created_at ON proctor_incidents(created_at DESC);

-- Incident evidence (file attachments)
CREATE TABLE IF NOT EXISTS incident_evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID NOT NULL REFERENCES proctor_incidents(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_incident_evidence_incident_id ON incident_evidence(incident_id);

-- ============================================================================
-- 6. Rate Limiting Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_key_window UNIQUE (key, window_start)
);

-- Indexes for rate_limits
CREATE INDEX idx_rate_limits_key ON rate_limits(key);
CREATE INDEX idx_rate_limits_window_end ON rate_limits(window_end);

-- Auto-cleanup expired rate limits (older than 1 hour)
CREATE INDEX idx_rate_limits_cleanup ON rate_limits(window_end)
    WHERE window_end < CURRENT_TIMESTAMP - INTERVAL '1 hour';

-- ============================================================================
-- 7. API Key Management Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    key_prefix VARCHAR(10) NOT NULL,  -- First 8 chars for identification
    name VARCHAR(255),
    tenant_id VARCHAR(255),
    tier api_key_tier NOT NULL DEFAULT 'FREE',
    scopes JSONB DEFAULT '["*"]',  -- Array of allowed scopes
    rate_limit_override INTEGER,  -- Custom rate limit
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for api_keys
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash) WHERE is_active = TRUE AND deleted_at IS NULL;
CREATE INDEX idx_api_keys_tenant_id ON api_keys(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at) WHERE is_active = TRUE;

-- ============================================================================
-- 8. Audit Log Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,  -- table name
    entity_id UUID,
    action VARCHAR(50) NOT NULL,  -- INSERT, UPDATE, DELETE
    user_id VARCHAR(255),
    tenant_id VARCHAR(255),
    changes JSONB,  -- Old and new values
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for audit_log
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- Partition by month for better performance
-- (Uncomment if needed for high-volume deployments)
-- CREATE TABLE audit_log_y2026m01 PARTITION OF audit_log
--     FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- ============================================================================
-- 9. Functions and Triggers
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_face_embeddings_updated_at
    BEFORE UPDATE ON face_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_voice_enrollments_updated_at
    BEFORE UPDATE ON voice_enrollments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_proctor_sessions_updated_at
    BEFORE UPDATE ON proctor_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rate_limits_updated_at
    BEFORE UPDATE ON rate_limits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at
    BEFORE UPDATE ON api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 10. Views for Analytics
-- ============================================================================

-- Enrollment statistics view
CREATE OR REPLACE VIEW v_enrollment_stats AS
SELECT
    COUNT(*) as total_enrollments,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT tenant_id) as unique_tenants,
    AVG(quality_score) as avg_quality_score,
    MIN(quality_score) as min_quality_score,
    MAX(quality_score) as max_quality_score,
    DATE_TRUNC('day', created_at) as enrollment_date
FROM face_embeddings
WHERE deleted_at IS NULL
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY enrollment_date DESC;

-- Proctoring incidents summary view
CREATE OR REPLACE VIEW v_incident_summary AS
SELECT
    ps.session_id,
    ps.user_id,
    ps.status,
    ps.risk_score,
    COUNT(pi.id) as total_incidents,
    COUNT(pi.id) FILTER (WHERE pi.severity = 'CRITICAL') as critical_incidents,
    COUNT(pi.id) FILTER (WHERE pi.severity = 'HIGH') as high_incidents,
    COUNT(pi.id) FILTER (WHERE pi.severity = 'MEDIUM') as medium_incidents,
    COUNT(pi.id) FILTER (WHERE pi.severity = 'LOW') as low_incidents,
    ps.created_at,
    ps.ended_at
FROM proctor_sessions ps
LEFT JOIN proctor_incidents pi ON ps.id = pi.session_id AND pi.deleted_at IS NULL
WHERE ps.deleted_at IS NULL
GROUP BY ps.id, ps.session_id, ps.user_id, ps.status, ps.risk_score, ps.created_at, ps.ended_at;

-- ============================================================================
-- 11. Maintenance Jobs (Run via pg_cron or external scheduler)
-- ============================================================================

-- Function to clean up expired rate limits
CREATE OR REPLACE FUNCTION cleanup_expired_rate_limits()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM rate_limits
    WHERE window_end < CURRENT_TIMESTAMP - INTERVAL '1 hour';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up soft-deleted records (older than 90 days)
CREATE OR REPLACE FUNCTION cleanup_soft_deleted_records()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    temp_count INTEGER;
BEGIN
    -- Clean up face_embeddings
    DELETE FROM face_embeddings
    WHERE deleted_at IS NOT NULL
    AND deleted_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;

    -- Clean up voice_enrollments
    DELETE FROM voice_enrollments
    WHERE deleted_at IS NOT NULL
    AND deleted_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;

    -- Clean up proctor_sessions
    DELETE FROM proctor_sessions
    WHERE deleted_at IS NOT NULL
    AND deleted_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;

    -- Clean up old audit logs (older than 1 year)
    DELETE FROM audit_log
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 year';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 12. Grants and Permissions
-- ============================================================================

-- Grant necessary permissions to biometric_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO biometric_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO biometric_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO biometric_user;

-- Grant usage on custom types
GRANT USAGE ON TYPE session_status TO biometric_user;
GRANT USAGE ON TYPE incident_type TO biometric_user;
GRANT USAGE ON TYPE incident_severity TO biometric_user;
GRANT USAGE ON TYPE review_action TO biometric_user;
GRANT USAGE ON TYPE api_key_tier TO biometric_user;

-- ============================================================================
-- Success Message
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully!';
    RAISE NOTICE 'Extensions: vector, uuid-ossp, pg_trgm';
    RAISE NOTICE 'Tables: face_embeddings, voice_enrollments, proctor_sessions, proctor_incidents, incident_evidence, rate_limits, api_keys, audit_log';
    RAISE NOTICE 'Views: v_enrollment_stats, v_incident_summary';
    RAISE NOTICE 'Functions: cleanup_expired_rate_limits, cleanup_soft_deleted_records';
END $$;
