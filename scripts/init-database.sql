-- Database Initialization Script for Biometric API
-- Run this script on Cloud SQL PostgreSQL to set up the required extensions and schema

-- ===========================================
-- Enable Required Extensions
-- ===========================================

-- Enable pgvector for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector CASCADE;

-- Verify extension is installed
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- ===========================================
-- Create Schema if not exists
-- ===========================================

-- Face embeddings table for enrollment
CREATE TABLE IF NOT EXISTS face_embeddings (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE NOT NULL,
    embedding vector(128) NOT NULL,  -- FaceNet produces 128-dimensional embeddings
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS face_embeddings_vector_idx
    ON face_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Create index on external_id for quick lookups
CREATE INDEX IF NOT EXISTS face_embeddings_external_id_idx
    ON face_embeddings (external_id);

-- ===========================================
-- Verification Queries
-- ===========================================

-- Check vector extension
SELECT 'pgvector extension' as check_name,
       CASE WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
            THEN 'OK' ELSE 'MISSING' END as status;

-- Check face_embeddings table
SELECT 'face_embeddings table' as check_name,
       CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'face_embeddings')
            THEN 'OK' ELSE 'MISSING' END as status;

-- Check vector index
SELECT 'vector index' as check_name,
       CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'face_embeddings_vector_idx')
            THEN 'OK' ELSE 'MISSING' END as status;

-- Show current row count
SELECT 'Current enrollments' as info, COUNT(*) as count FROM face_embeddings;
