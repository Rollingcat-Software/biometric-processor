-- Add HNSW indexes for face_embeddings, voice_enrollments, and fingerprint_enrollments.
-- Run once on the biometric_db database via:
--   docker exec -i shared-postgres psql -U postgres -d biometric_db < scripts/add_hnsw_indexes.sql
--
-- The biometric_data table (alembic migration) already has an HNSW index
-- (ix_biometric_data_embedding_hnsw).  The face_embeddings table (init.sql)
-- only had an IVFFlat index -- this script upgrades it to HNSW.
-- Voice and fingerprint tables were added later without vector indexes.

-- pgvector extension should already exist; ensure it does
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- face_embeddings HNSW index (replaces the slower IVFFlat index from init.sql)
-- ============================================================================
-- Drop the old IVFFlat index if it exists, then create HNSW
DROP INDEX IF EXISTS idx_embeddings_vector;

CREATE INDEX IF NOT EXISTS idx_face_embeddings_embedding_hnsw
    ON face_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- voice_enrollments HNSW index
-- ============================================================================
-- Speeds up cosine-distance searches in voice 1:N identification
-- and centroid lookups.  Parameters: m=16 connections, ef_construction=64.
CREATE INDEX IF NOT EXISTS idx_voice_enrollments_embedding_hnsw
    ON voice_enrollments
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- B-tree helper indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_voice_enrollments_user_type
    ON voice_enrollments (user_id, enrollment_type)
    WHERE deleted_at IS NULL;

-- ============================================================================
-- fingerprint_enrollments HNSW index (kept for schema completeness,
-- even though fingerprint endpoints now return 501)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_fingerprint_enrollments_embedding_hnsw
    ON fingerprint_enrollments
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_fingerprint_enrollments_user_type
    ON fingerprint_enrollments (user_id, enrollment_type)
    WHERE deleted_at IS NULL;

-- Update statistics for the query planner
ANALYZE face_embeddings;
ANALYZE voice_enrollments;
ANALYZE fingerprint_enrollments;

SELECT 'HNSW indexes created successfully' AS status;
