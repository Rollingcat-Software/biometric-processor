-- Migration: Create proctoring service tables
-- Version: 003
-- Description: Add proctoring sessions, incidents, and evidence tables

-- Proctor Sessions
CREATE TABLE IF NOT EXISTS proctor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    risk_score FLOAT NOT NULL DEFAULT 0.0,
    config JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    baseline_embedding JSONB,
    verification_count INTEGER NOT NULL DEFAULT 0,
    verification_failures INTEGER NOT NULL DEFAULT 0,
    incident_count INTEGER NOT NULL DEFAULT 0,
    total_gaze_away_sec FLOAT NOT NULL DEFAULT 0.0,
    termination_reason VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    paused_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Session indexes
CREATE INDEX IF NOT EXISTS idx_proctor_sessions_exam
    ON proctor_sessions(exam_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_proctor_sessions_user
    ON proctor_sessions(user_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_proctor_sessions_status
    ON proctor_sessions(status, tenant_id);

CREATE INDEX IF NOT EXISTS idx_proctor_sessions_active
    ON proctor_sessions(tenant_id)
    WHERE status IN ('active', 'flagged');

CREATE INDEX IF NOT EXISTS idx_proctor_sessions_created
    ON proctor_sessions(created_at DESC);

-- Proctor Incidents
CREATE TABLE IF NOT EXISTS proctor_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(255),
    review_action VARCHAR(50),
    review_notes TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Incident indexes
CREATE INDEX IF NOT EXISTS idx_proctor_incidents_session
    ON proctor_incidents(session_id);

CREATE INDEX IF NOT EXISTS idx_proctor_incidents_severity
    ON proctor_incidents(session_id, severity);

CREATE INDEX IF NOT EXISTS idx_proctor_incidents_unreviewed
    ON proctor_incidents(session_id)
    WHERE reviewed = FALSE;

CREATE INDEX IF NOT EXISTS idx_proctor_incidents_type_time
    ON proctor_incidents(session_id, incident_type, timestamp DESC);

-- Incident Evidence
CREATE TABLE IF NOT EXISTS incident_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES proctor_incidents(id) ON DELETE CASCADE,
    evidence_type VARCHAR(50) NOT NULL,
    storage_url TEXT NOT NULL,
    thumbnail_url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incident_evidence_incident
    ON incident_evidence(incident_id);

-- Verification Events (sampled for analytics)
CREATE TABLE IF NOT EXISTS verification_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    face_detected BOOLEAN NOT NULL,
    face_matched BOOLEAN NOT NULL,
    confidence FLOAT NOT NULL,
    liveness_score FLOAT,
    quality_score FLOAT,
    face_count INTEGER NOT NULL DEFAULT 1,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_events_session
    ON verification_events(session_id, timestamp);

-- Session Config Templates
CREATE TABLE IF NOT EXISTS session_config_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE(tenant_id, name)
);

-- Comments for documentation
COMMENT ON TABLE proctor_sessions IS 'Proctoring session records for continuous identity verification';
COMMENT ON TABLE proctor_incidents IS 'Detected incidents during proctoring sessions';
COMMENT ON TABLE incident_evidence IS 'Evidence files attached to incidents';
COMMENT ON TABLE verification_events IS 'Sampled verification events for analytics';
COMMENT ON TABLE session_config_templates IS 'Reusable session configuration templates';

COMMENT ON COLUMN proctor_sessions.status IS 'Session status: created, initializing, active, paused, flagged, completed, terminated, expired';
COMMENT ON COLUMN proctor_sessions.risk_score IS 'Aggregated risk score (0.0-1.0)';
COMMENT ON COLUMN proctor_incidents.severity IS 'Incident severity: low, medium, high, critical';
COMMENT ON COLUMN proctor_incidents.incident_type IS 'Type of incident detected';
