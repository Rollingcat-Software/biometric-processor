# Enable PostgreSQL Database - Quick Start Guide

This guide will help you switch from in-memory to PostgreSQL + pgvector storage.

## Prerequisites

- Docker and Docker Compose installed
- Port 5432 available
- ~500MB disk space for PostgreSQL

---

## Step 1: Start PostgreSQL

```bash
# Start PostgreSQL with pgvector
docker-compose up -d postgres

# Wait for it to be healthy (30-60 seconds)
docker-compose ps postgres

# Check logs
docker-compose logs postgres
```

**Expected output:**
```
postgres  | PostgreSQL init process complete; ready for start up
postgres  | database system is ready to accept connections
```

---

## Step 2: Fix Schema Mismatch

The migration creates `face_embeddings` but the repository expects `biometric_data`.

**Option A: Update migration to create biometric_data (RECOMMENDED)**

Edit: `alembic/versions/20251212_0001_initial_schema.py`

Change line 60 from:
```python
op.create_table("face_embeddings",  # ❌ OLD
```

To:
```python
op.create_table("biometric_data",  # ✅ NEW
```

And update all references to `face_embeddings` to `biometric_data` in the migration.

**Option B: Update repository to use face_embeddings**

Edit: `app/infrastructure/persistence/repositories/pgvector_embedding_repository.py`

Change all SQL queries from `biometric_data` to `face_embeddings`.

---

## Step 3: Run Database Migrations

```bash
# Apply schema
alembic upgrade head

# Verify
alembic current
# Should show: 0001_initial (head)
```

---

## Step 4: Create Vector Index

Connect to PostgreSQL and create the vector index:

```bash
# Connect to database
docker-compose exec postgres psql -U biometric -d biometric

# Create HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_biometric_embedding_hnsw
ON biometric_data
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

# Verify index
\di idx_biometric_embedding_hnsw

# Exit
\q
```

**Index Options:**

- **HNSW** (Hierarchical Navigable Small World):
  - Best for: High accuracy, moderate dataset size
  - Parameters: `m=16, ef_construction=64`
  - Build time: Slower
  - Query time: Faster

- **IVFFlat** (Inverted File Flat):
  - Best for: Large datasets, acceptable accuracy
  - Parameters: `lists=100` (adjust based on dataset size)
  - Build time: Faster
  - Query time: Moderate

---

## Step 5: Enable pgvector in Configuration

```bash
# Create .env file if it doesn't exist
cp .env.example .env

# Edit .env and set:
USE_PGVECTOR=True
DATABASE_URL=postgresql://biometric:biometric@localhost:5432/biometric
EMBEDDING_DIMENSION=128  # Match your FACE_RECOGNITION_MODEL

# Model dimensions:
# - Facenet: 128
# - Facenet512: 512
# - VGG-Face: 2622
# - ArcFace: 512
```

**IMPORTANT:** `EMBEDDING_DIMENSION` must match your face recognition model!

---

## Step 6: Restart the API

```bash
# Stop current server (Ctrl+C)

# Start with new configuration
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
INFO: InMemoryEmbeddingRepository initialized  # ❌ Wrong - still in-memory
```

---

## Step 7: Verify Database Integration

### Test 1: Enroll a face

```bash
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "file=@test_face.jpg" \
  -F "user_id=test_user_001"
```

### Test 2: Check PostgreSQL

```bash
docker-compose exec postgres psql -U biometric -d biometric -c \
  "SELECT user_id, quality_score, embedding_dimension FROM biometric_data;"
```

**Expected output:**
```
    user_id     | quality_score | embedding_dimension
----------------+---------------+--------------------
 test_user_001  |          85.5 |                128
```

### Test 3: Verify persistence

```bash
# Restart the API
# Ctrl+C to stop
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Try to verify the enrolled user (should still exist!)
curl -X POST "http://localhost:8001/api/v1/verify" \
  -F "file=@test_face.jpg" \
  -F "user_id=test_user_001"
```

**Expected:** `"verified": true` ✅

With in-memory mode, this would fail after restart!

---

## Troubleshooting

### Issue: "connection refused"

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Issue: "pgvector extension not found"

```bash
# Create extension manually
docker-compose exec postgres psql -U biometric -d biometric -c \
  "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Issue: "Embedding dimension mismatch"

Check your model vs configuration:

```bash
# In .env, match these:
FACE_RECOGNITION_MODEL=Facenet      # 128 dimensions
EMBEDDING_DIMENSION=128              # Must match!

# Or:
FACE_RECOGNITION_MODEL=Facenet512   # 512 dimensions
EMBEDDING_DIMENSION=512              # Must match!
```

### Issue: "Table biometric_data does not exist"

You didn't fix the schema mismatch. Go back to Step 2.

---

## Performance Tuning

### For large datasets (10K+ faces):

```sql
-- Optimize for large datasets
ALTER TABLE biometric_data SET (autovacuum_vacuum_scale_factor = 0.01);

-- Increase work_mem for index builds
SET work_mem = '256MB';

-- Rebuild index
REINDEX INDEX idx_biometric_embedding_hnsw;
```

### Connection pool tuning:

```bash
# In .env:
DATABASE_POOL_MIN_SIZE=20   # Increase for high traffic
DATABASE_POOL_MAX_SIZE=50   # Max concurrent connections
```

---

## Rollback to In-Memory

If you need to go back to in-memory mode:

```bash
# Edit .env
USE_PGVECTOR=False

# Restart API
# Data in PostgreSQL is preserved, just not used
```

---

## Next Steps

Once database integration is working:

1. ✅ **Backup strategy**: Set up automated PostgreSQL backups
2. ✅ **Monitoring**: Add pgvector query performance monitoring
3. ✅ **Scaling**: Configure read replicas for high-traffic scenarios
4. ✅ **Index tuning**: Adjust HNSW parameters based on dataset size
5. ✅ **Multi-tenancy**: Test tenant isolation

---

## Summary

- ✅ PostgreSQL with pgvector provides persistent, scalable embedding storage
- ✅ Vector indexes enable fast similarity search (< 10ms for 1M faces)
- ✅ Multi-tenancy support for SaaS deployments
- ✅ ACID compliance for data consistency
- ✅ Production-ready with connection pooling

**Your face embeddings will now persist across restarts!** 🎉
