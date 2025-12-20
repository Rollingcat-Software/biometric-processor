-- Migration: 001_create_proctor_tables
-- Description: Create proctoring service tables
-- Created: 2024-12-12

-- Proctor Sessions Table
CREATE TABLE IF NOT EXISTS proctor_sessions (
    id UUID PRIMARY KEY,
    exam_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    risk_score FLOAT DEFAULT 0.0,
    config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    baseline_embedding JSONB,
    verification_count INTEGER DEFAULT 0,
    verification_failures INTEGER DEFAULT 0,
    incident_count INTEGER DEFAULT 0,
    total_gaze_away_sec FLOAT DEFAULT 0.0,
    termination_reason VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    paused_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraint to prevent duplicate sessions for same exam/user/tenant
    CONSTRAINT unique_exam_user_tenant UNIQUE (exam_id, user_id, tenant_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_status ON proctor_sessions(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_exam ON proctor_sessions(exam_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON proctor_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON proctor_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_created ON proctor_sessions(tenant_id, created_at DESC);

-- Proctor Incidents Table
CREATE TABLE IF NOT EXISTS proctor_incidents (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    details JSONB DEFAULT '{}',
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(255),
    review_action VARCHAR(50),
    review_notes TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for incidents
CREATE INDEX IF NOT EXISTS idx_incidents_session ON proctor_incidents(session_id);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON proctor_incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_reviewed ON proctor_incidents(reviewed);
CREATE INDEX IF NOT EXISTS idx_incidents_type ON proctor_incidents(incident_type);
CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON proctor_incidents(session_id, timestamp DESC);

-- Incident Evidence Table
CREATE TABLE IF NOT EXISTS incident_evidence (
    id UUID PRIMARY KEY,
    incident_id UUID NOT NULL REFERENCES proctor_incidents(id) ON DELETE CASCADE,
    evidence_type VARCHAR(50) NOT NULL,
    storage_url TEXT NOT NULL,
    thumbnail_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for evidence lookup
CREATE INDEX IF NOT EXISTS idx_evidence_incident ON incident_evidence(incident_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_proctor_sessions_updated_at ON proctor_sessions;
CREATE TRIGGER update_proctor_sessions_updated_at
    BEFORE UPDATE ON proctor_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE proctor_sessions IS 'Proctoring sessions for exam monitoring';
COMMENT ON TABLE proctor_incidents IS 'Incidents detected during proctoring sessions';
COMMENT ON TABLE incident_evidence IS 'Evidence files associated with incidents';

COMMENT ON COLUMN proctor_sessions.status IS 'Session status: created, active, paused, flagged, ended, terminated';
COMMENT ON COLUMN proctor_sessions.risk_score IS 'Cumulative risk score from 0.0 to 1.0';
COMMENT ON COLUMN proctor_sessions.termination_reason IS 'Reason for termination if terminated early';

COMMENT ON COLUMN proctor_incidents.incident_type IS 'Type: face_not_detected, multiple_faces, gaze_away, phone_detected, etc';
COMMENT ON COLUMN proctor_incidents.severity IS 'Severity: info, low, medium, high, critical';
COMMENT ON COLUMN proctor_incidents.review_action IS 'Action taken: dismiss, confirm, escalate';
