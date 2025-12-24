# Database Integration Testing Guide

**Date:** 2025-12-24
**Status:** Ready for Testing

This guide helps you test the complete PostgreSQL + pgvector database integration.

---

## 🚀 Quick Test (Automated)

**One command to test everything:**

```bash
./test_database_integration.sh
```

This script will:
1. ✅ Start PostgreSQL
2. ✅ Run migrations
3. ✅ Verify schema
4. ✅ Test CRUD operations
5. ✅ Test vector similarity search
6. ✅ Verify indexes and constraints

**Expected output:**
```
================================
Database Integration Test
================================

✅ Docker is installed
✅ PostgreSQL is ready
✅ Migration completed successfully
✅ biometric_data table exists
✅ All required columns exist
✅ HNSW vector index exists
✅ INSERT successful
✅ SELECT successful
✅ Vector similarity search successful
✅ UPDATE successful
✅ Soft DELETE successful

All database integration tests passed! 🎉
```

---

## 📋 Manual Testing Steps

If you prefer to test manually, follow these steps:

### **Step 1: Start PostgreSQL**

```bash
# Start PostgreSQL container
docker compose up -d postgres

# Wait for it to be ready
docker compose ps postgres

# Check logs
docker compose logs postgres
```

**Expected:** PostgreSQL should be running and healthy.

---

### **Step 2: Verify pgvector Extension**

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U biometric -d postgres

# Check pgvector is available
SELECT * FROM pg_available_extensions WHERE name = 'vector';

# Exit
\q
```

**Expected:** You should see the `vector` extension listed.

---

### **Step 3: Run Database Migration**

```bash
# Check current migration status
alembic current

# Run migration
alembic upgrade head

# Verify migration applied
alembic current
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial
```

---

### **Step 4: Verify Schema Created**

```bash
# Connect to database
docker compose exec postgres psql -U biometric -d biometric

# List tables
\dt

# Describe biometric_data table
\d biometric_data

# List indexes
\di
```

**Expected tables:**
- `biometric_data` ✅
- `proctor_sessions` ✅
- `proctor_incidents` ✅
- `incident_evidence` ✅

**Expected columns in biometric_data:**
```
 Column          | Type                     | Nullable | Default
-----------------+--------------------------+----------+-------------------
 id              | uuid                     | not null | gen_random_uuid()
 tenant_id       | uuid                     |          |
 user_id         | character varying(255)   | not null |
 biometric_type  | character varying(50)    | not null | 'FACE'
 embedding       | vector(512)              |          |
 embedding_model | character varying(100)   | not null | 'Facenet512'
 quality_score   | double precision         | not null |
 is_active       | boolean                  | not null | true
 is_primary      | boolean                  | not null | true
 deleted_at      | timestamp with time zone |          |
 created_at      | timestamp with time zone | not null | now()
 updated_at      | timestamp with time zone | not null | now()
```

**Expected indexes:**
- `ix_biometric_data_embedding_hnsw` (HNSW index) ✅
- `ix_biometric_data_user_tenant_type_active` (Unique constraint) ✅
- `ix_biometric_data_tenant_id` ✅
- `ix_biometric_data_user_id` ✅
- `ix_biometric_data_tenant_user` ✅
- `ix_biometric_data_active` ✅
- `ix_biometric_data_type` ✅

---

### **Step 5: Test CRUD Operations**

```sql
-- Still in psql

-- INSERT test data
INSERT INTO biometric_data (
    id, user_id, tenant_id, biometric_type, embedding_model,
    quality_score, is_active, is_primary, embedding
) VALUES (
    gen_random_uuid(),
    'test_user_001',
    NULL,
    'FACE',
    'Facenet512',
    0.95,
    TRUE,
    TRUE,
    array_fill(0.5::float, ARRAY[512])::vector(512)
);

-- SELECT test data
SELECT user_id, biometric_type, embedding_model, quality_score
FROM biometric_data
WHERE user_id = 'test_user_001';

-- Expected output:
--    user_id     | biometric_type | embedding_model | quality_score
-- ---------------+----------------+-----------------+---------------
--  test_user_001 | FACE           | Facenet512      |          0.95

-- UPDATE test
UPDATE biometric_data
SET quality_score = 0.99
WHERE user_id = 'test_user_001';

-- Verify update
SELECT user_id, quality_score FROM biometric_data WHERE user_id = 'test_user_001';

-- Soft DELETE test
UPDATE biometric_data
SET deleted_at = CURRENT_TIMESTAMP, is_active = FALSE
WHERE user_id = 'test_user_001';

-- Verify soft delete
SELECT user_id, is_active, deleted_at FROM biometric_data WHERE user_id = 'test_user_001';
```

---

### **Step 6: Test Vector Similarity Search**

```sql
-- Test cosine distance operator
SELECT
    user_id,
    embedding <=> array_fill(0.5::float, ARRAY[512])::vector(512) AS distance
FROM biometric_data
WHERE deleted_at IS NULL
ORDER BY distance
LIMIT 5;

-- Expected: Results ordered by similarity (lowest distance = most similar)
```

---

### **Step 7: Test Vector Index Performance**

```sql
-- Explain query to verify index is used
EXPLAIN ANALYZE
SELECT user_id
FROM biometric_data
WHERE embedding <=> array_fill(0.5::float, ARRAY[512])::vector(512) < 0.5
ORDER BY embedding <=> array_fill(0.5::float, ARRAY[512])::vector(512)
LIMIT 10;

-- Expected: Query plan should show "Index Scan using ix_biometric_data_embedding_hnsw"
```

---

### **Step 8: Clean Up Test Data**

```sql
-- Delete test data
DELETE FROM biometric_data WHERE user_id = 'test_user_001';

-- Verify cleanup
SELECT COUNT(*) FROM biometric_data;

-- Exit psql
\q
```

---

## 🔧 Testing with the API

### **Step 1: Enable pgvector**

```bash
# Create or update .env file
echo "USE_PGVECTOR=True" >> .env
echo "DATABASE_URL=postgresql://biometric:biometric@localhost:5432/biometric" >> .env
echo "EMBEDDING_DIMENSION=512" >> .env  # Must match your model
```

### **Step 2: Start the API**

```bash
# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Look for these log messages:**
```
INFO: Creating PostgreSQL connection pool...
INFO: PostgreSQL connection pool created successfully
INFO: PgVectorEmbeddingRepository initialized
```

**NOT:**
```
INFO: InMemoryEmbeddingRepository initialized  # ❌ Wrong - still using in-memory
```

---

### **Step 3: Test Enrollment (Save to Database)**

```bash
# Enroll a test user
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "file=@test_face.jpg" \
  -F "user_id=api_test_001"
```

**Expected response:**
```json
{
  "user_id": "api_test_001",
  "enrolled": true,
  "quality_score": 0.85
}
```

---

### **Step 4: Verify Data in Database**

```bash
# Check database
docker compose exec postgres psql -U biometric -d biometric -c \
  "SELECT user_id, biometric_type, embedding_model, quality_score FROM biometric_data WHERE user_id = 'api_test_001';"
```

**Expected:**
```
    user_id     | biometric_type | embedding_model | quality_score
----------------+----------------+-----------------+---------------
 api_test_001   | FACE           | Facenet512      |          0.85
```

---

### **Step 5: Test Verification**

```bash
# Verify the enrolled user
curl -X POST "http://localhost:8001/api/v1/verify" \
  -F "file=@test_face.jpg" \
  -F "user_id=api_test_001"
```

**Expected response:**
```json
{
  "verified": true,
  "user_id": "api_test_001",
  "similarity": 0.95,
  "confidence": 0.98
}
```

---

### **Step 6: Test Persistence (Critical!)**

```bash
# Restart the API
# Press Ctrl+C to stop
# Then restart:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Try verification again (should still work!)
curl -X POST "http://localhost:8001/api/v1/verify" \
  -F "file=@test_face.jpg" \
  -F "user_id=api_test_001"
```

**Expected:** `"verified": true` ✅

**With in-memory mode, this would FAIL after restart!**

---

### **Step 7: Test Face Search (1:N)**

```bash
# Search for similar faces
curl -X POST "http://localhost:8001/api/v1/search" \
  -F "file=@test_face.jpg" \
  -F "threshold=0.6" \
  -F "limit=5"
```

**Expected response:**
```json
{
  "matches": [
    {
      "user_id": "api_test_001",
      "similarity": 0.95,
      "distance": 0.05
    }
  ],
  "count": 1
}
```

---

## 🔍 Troubleshooting

### **Issue: "connection refused"**

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Restart
docker compose restart postgres
```

---

### **Issue: "pgvector extension not found"**

```bash
# Create extension manually
docker compose exec postgres psql -U biometric -d biometric -c \
  "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

### **Issue: "Table biometric_data does not exist"**

```bash
# Check current migration
alembic current

# If not applied, run migration
alembic upgrade head
```

---

### **Issue: "Embedding dimension mismatch"**

```bash
# Check your model configuration
grep FACE_MODEL .env
grep EMBEDDING_DIMENSION .env

# Models and their dimensions:
# Facenet: 128
# Facenet512: 512
# VGG-Face: 2622
# ArcFace: 512

# Make sure they match!
```

---

### **Issue: "Still using InMemoryEmbeddingRepository"**

```bash
# Verify .env settings
cat .env | grep USE_PGVECTOR

# Should show: USE_PGVECTOR=True

# If not, add it:
echo "USE_PGVECTOR=True" >> .env

# Restart API
```

---

## ✅ Success Criteria

Database integration is successful if:

1. ✅ PostgreSQL starts without errors
2. ✅ Migration runs successfully (alembic upgrade head)
3. ✅ biometric_data table exists with all columns
4. ✅ HNSW vector index exists
5. ✅ Can INSERT embeddings
6. ✅ Can SELECT embeddings
7. ✅ Vector similarity search works
8. ✅ API shows "PgVectorEmbeddingRepository initialized"
9. ✅ Enrollment saves to database
10. ✅ Verification works after API restart (persistence!)

---

## 📊 Performance Benchmarks

After successful integration, you should see:

| Operation | Performance | Notes |
|-----------|-------------|-------|
| Enrollment (INSERT) | < 50ms | Single row insert |
| Verification (1:1) | < 10ms | Indexed lookup by user_id |
| Search (1:N, 1K faces) | < 5ms | HNSW index |
| Search (1:N, 100K faces) | < 20ms | HNSW approximate search |

---

## 🎉 Next Steps

Once database integration is verified:

1. ✅ Set up automated backups
2. ✅ Configure monitoring (connection pool stats)
3. ✅ Test with large datasets (1M+ faces)
4. ✅ Tune HNSW parameters if needed
5. ✅ Set up read replicas for high availability

---

## 📚 Additional Resources

- **Port Standards:** See `PORT_STANDARDS.md`
- **Database Setup:** See `ENABLE_DATABASE.md`
- **Fixes Applied:** See `DATABASE_FIXES_APPLIED.md`
- **Automated Test Script:** `./test_database_integration.sh`

---

**Ready to test? Run:**

```bash
./test_database_integration.sh
```

**Or test manually following the steps above!** 🚀
