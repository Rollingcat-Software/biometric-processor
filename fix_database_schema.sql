-- Fix for Database Schema Mismatch
-- The repository queries 'face_embeddings' but migration creates 'biometric_data'
-- This script creates a view to bridge the gap

-- Drop view if exists
DROP VIEW IF EXISTS face_embeddings;

-- Create view that maps biometric_data to face_embeddings
CREATE OR REPLACE VIEW face_embeddings AS
SELECT
    id,
    user_id,
    tenant_id,
    embedding,
    quality_score,
    created_at,
    updated_at
FROM biometric_data
WHERE deleted_at IS NULL;

-- Create INSTEAD OF triggers to make the view updatable
-- This allows INSERT/UPDATE/DELETE operations through the view

-- INSERT trigger
CREATE OR REPLACE FUNCTION face_embeddings_insert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO biometric_data (
        user_id,
        tenant_id,
        embedding,
        quality_score,
        biometric_type,
        embedding_model,
        is_active,
        is_primary
    ) VALUES (
        NEW.user_id,
        NEW.tenant_id,
        NEW.embedding,
        NEW.quality_score,
        'FACE',
        'Facenet512',
        TRUE,
        TRUE
    )
    ON CONFLICT (user_id, tenant_id, biometric_type)
    WHERE deleted_at IS NULL
    DO UPDATE SET
        embedding = EXCLUDED.embedding,
        quality_score = EXCLUDED.quality_score,
        updated_at = CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER face_embeddings_insert_trigger
INSTEAD OF INSERT ON face_embeddings
FOR EACH ROW
EXECUTE FUNCTION face_embeddings_insert();

-- UPDATE trigger
CREATE OR REPLACE FUNCTION face_embeddings_update()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE biometric_data
    SET
        embedding = NEW.embedding,
        quality_score = NEW.quality_score,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        user_id = NEW.user_id
        AND (tenant_id = NEW.tenant_id OR (tenant_id IS NULL AND NEW.tenant_id IS NULL))
        AND deleted_at IS NULL;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER face_embeddings_update_trigger
INSTEAD OF UPDATE ON face_embeddings
FOR EACH ROW
EXECUTE FUNCTION face_embeddings_update();

-- DELETE trigger
CREATE OR REPLACE FUNCTION face_embeddings_delete()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE biometric_data
    SET
        deleted_at = CURRENT_TIMESTAMP,
        is_active = FALSE
    WHERE
        user_id = OLD.user_id
        AND (tenant_id = OLD.tenant_id OR (tenant_id IS NULL AND OLD.tenant_id IS NULL))
        AND deleted_at IS NULL;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER face_embeddings_delete_trigger
INSTEAD OF DELETE ON face_embeddings
FOR EACH ROW
EXECUTE FUNCTION face_embeddings_delete();

-- Verify the view works
SELECT 'View created successfully. Testing...' AS status;

-- Show current data
SELECT COUNT(*) as total_records FROM biometric_data;
SELECT COUNT(*) as visible_records FROM face_embeddings;

SELECT 'Setup complete!' AS status;
