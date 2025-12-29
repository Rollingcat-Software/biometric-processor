# Batch Processing Endpoints - Architecture & Data Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT REQUEST                            │
│  POST /api/v1/batch/enroll                                       │
│  - files: [image1.jpg, image2.jpg, ...]                          │
│  - items: [{"user_id": "user1"}, {"user_id": "user2"}, ...]      │
│  - skip_duplicates: true/false                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API ROUTE LAYER                              │
│  app/api/routes/batch.py                                         │
│                                                                  │
│  ✓ Validate batch size (max 50)                                 │
│  ✓ Validate total file size (max 50MB)                          │
│  ✓ Parse JSON items                                             │
│  ✓ Validate file count = items count                            │
│  ✓ Save files to temp storage                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   USE CASE LAYER                                 │
│  app/application/use_cases/batch_process.py                      │
│                                                                  │
│  BatchEnrollmentUseCase.execute():                               │
│  ┌──────────────────────────────────────────────────┐           │
│  │ For each item:                                    │           │
│  │   1. Detect face (IFaceDetector)                 │           │
│  │   2. Extract embedding (IEmbeddingExtractor)     │           │
│  │   3. Assess quality (IQualityAssessor)           │           │
│  │   4. Save to repository (IEmbeddingRepository)   │           │
│  │   5. Track result (success/failed/skipped)       │           │
│  └──────────────────────────────────────────────────┘           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 REPOSITORY LAYER                                 │
│  app/infrastructure/persistence/repositories/                    │
│  pgvector_embedding_repository.py                                │
│                                                                  │
│  PgVectorEmbeddingRepository.save():                             │
│  ┌──────────────────────────────────────────────────┐           │
│  │ 1. Convert numpy array to list                   │           │
│  │    embedding_list = embedding.tolist()           │           │
│  │                                                   │           │
│  │ 2. Execute SQL INSERT/UPDATE                     │           │
│  │    INSERT INTO face_embeddings                   │           │
│  │    VALUES ($1, $2, $3, $4)  ◄── ISSUE HERE!     │           │
│  │                                                   │           │
│  │    $3 = embedding_list (Python list)             │           │
│  │    But asyncpg doesn't know how to convert       │           │
│  │    list → vector(512) without pgvector package   │           │
│  └──────────────────────────────────────────────────┘           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DATABASE LAYER                                 │
│  PostgreSQL with pgvector extension                              │
│                                                                  │
│  Table: face_embeddings                                          │
│  ┌────────────┬──────────────┬──────────────┐                   │
│  │ user_id    │ embedding    │ quality_score│                   │
│  │ (varchar)  │ (vector(512))│ (float)      │                   │
│  └────────────┴──────────────┴──────────────┘                   │
│                                                                  │
│  ERROR: Cannot accept Python list for vector(512) column        │
│  Needs: pgvector type registration in asyncpg connection        │
└─────────────────────────────────────────────────────────────────┘
```

## The Problem

```
┌──────────────────────────────────────────────────────────────────┐
│                      CURRENT STATE (BROKEN)                       │
└──────────────────────────────────────────────────────────────────┘

Python Code (Repository):
    embedding_list = [0.1, 0.2, 0.3, ..., 0.512]  # Python list
    await conn.execute(
        "INSERT INTO face_embeddings (embedding) VALUES ($1)",
        embedding_list  # asyncpg doesn't know this is a vector type!
    )

asyncpg:
    ❌ ERROR: "expected str, got list"
    (Doesn't know how to convert Python list → PostgreSQL vector)

PostgreSQL:
    ❌ Never receives the data
    (Type conversion fails at driver level)
```

## The Solution

```
┌──────────────────────────────────────────────────────────────────┐
│                       FIXED STATE                                 │
└──────────────────────────────────────────────────────────────────┘

Step 1: Install pgvector package
    pip install pgvector>=0.2.4

Step 2: Register vector type in connection setup
    async def _setup_connection(self, conn: asyncpg.Connection):
        from pgvector.asyncpg import register_vector
        await register_vector(conn)  # ← This registers the type handler
        ...

Step 3: Now asyncpg knows how to convert Python list → vector
    embedding_list = [0.1, 0.2, ..., 0.512]
    await conn.execute(
        "INSERT INTO face_embeddings (embedding) VALUES ($1)",
        embedding_list  # asyncpg converts this to vector(512) ✓
    )

asyncpg:
    ✓ Converts Python list → pgvector format
    ✓ Sends to PostgreSQL as proper vector type

PostgreSQL:
    ✓ Receives data in correct format
    ✓ Stores in vector(512) column
    ✓ Can use vector indexes for similarity search
```

## Data Flow (After Fix)

```
┌─────────────────────────────────────────────────────────────────┐
│  Batch Enrollment Request (3 images)                             │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │  Route: Validate & Save to temp storage      │
    │  Time: ~100ms                                 │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │  Use Case: Process each image in parallel    │
    │  ┌────────────┐ ┌────────────┐ ┌───────────┐│
    │  │ Image 1    │ │ Image 2    │ │ Image 3   ││
    │  │            │ │            │ │           ││
    │  │ Detect     │ │ Detect     │ │ Detect    ││
    │  │ ~200ms     │ │ ~200ms     │ │ ~200ms    ││
    │  │            │ │            │ │           ││
    │  │ Extract    │ │ Extract    │ │ Extract   ││
    │  │ ~300ms     │ │ ~300ms     │ │ ~300ms    ││
    │  │            │ │            │ │           ││
    │  │ Quality    │ │ Quality    │ │ Quality   ││
    │  │ ~50ms      │ │ ~50ms      │ │ ~50ms     ││
    │  │            │ │            │ │           ││
    │  │ Save DB    │ │ Save DB    │ │ Save DB   ││
    │  │ ~10ms      │ │ ~10ms      │ │ ~10ms     ││
    │  └────┬───────┘ └─────┬──────┘ └─────┬─────┘│
    │       │               │              │       │
    │       └───────────────┴──────────────┘       │
    │  Total: ~560ms (parallel) vs ~1680ms (seq)   │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │  Response: Aggregated results                │
    │  {                                            │
    │    "total_items": 3,                          │
    │    "successful": 3,                           │
    │    "failed": 0,                               │
    │    "results": [...]                           │
    │  }                                            │
    └───────────────────────────────────────────────┘
```

## Performance Comparison

```
┌──────────────────────────────────────────────────────────────────┐
│                  INDIVIDUAL REQUESTS (3 enrollments)              │
└──────────────────────────────────────────────────────────────────┘

Request 1: POST /enroll (image1)
├─ HTTP overhead: 50ms
├─ Processing: 560ms
└─ Total: 610ms

Request 2: POST /enroll (image2)
├─ HTTP overhead: 50ms
├─ Processing: 560ms
└─ Total: 610ms

Request 3: POST /enroll (image3)
├─ HTTP overhead: 50ms
├─ Processing: 560ms
└─ Total: 610ms

TOTAL TIME: 1830ms (sequential)

┌──────────────────────────────────────────────────────────────────┐
│                   BATCH REQUEST (3 enrollments)                   │
└──────────────────────────────────────────────────────────────────┘

Single Request: POST /batch/enroll (3 images)
├─ HTTP overhead: 50ms
├─ Processing (parallel): 560ms
└─ Total: 610ms

TOTAL TIME: 610ms

IMPROVEMENT: 67% faster (1220ms saved)
```

## Request/Response Format

### Batch Enrollment Request
```
POST /api/v1/batch/enroll
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="files"; filename="image1.jpg"
Content-Type: image/jpeg

<binary data>
--boundary
Content-Disposition: form-data; name="files"; filename="image2.jpg"
Content-Type: image/jpeg

<binary data>
--boundary
Content-Disposition: form-data; name="items"

[
  {"user_id": "user1", "tenant_id": "tenant1"},
  {"user_id": "user2", "tenant_id": "tenant1"}
]
--boundary
Content-Disposition: form-data; name="skip_duplicates"

false
--boundary--
```

### Batch Enrollment Response
```json
{
  "total_items": 2,
  "successful": 2,
  "failed": 0,
  "skipped": 0,
  "results": [
    {
      "item_id": "user1",
      "status": "success",
      "data": {
        "enrollment_id": "uuid-1234",
        "quality_score": 87.3,
        "face_detected": true
      },
      "error": null,
      "error_code": null
    },
    {
      "item_id": "user2",
      "status": "success",
      "data": {
        "enrollment_id": "uuid-5678",
        "quality_score": 92.1,
        "face_detected": true
      },
      "error": null,
      "error_code": null
    }
  ],
  "message": "Batch enrollment completed: 2 successful, 0 failed, 0 skipped"
}
```

### Batch Verification Request
```
POST /api/v1/batch/verify
Content-Type: multipart/form-data

[Similar to enrollment, with additional item_id field]
items: [
  {"item_id": "verify1", "user_id": "user1"},
  {"item_id": "verify2", "user_id": "user2"}
]
threshold: 0.6
```

### Batch Verification Response
```json
{
  "total_items": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "item_id": "verify1",
      "status": "success",
      "data": {
        "matched": true,
        "similarity": 0.85,
        "confidence": 95.2,
        "user_id": "user1"
      },
      "error": null,
      "error_code": null
    },
    {
      "item_id": "verify2",
      "status": "success",
      "data": {
        "matched": false,
        "similarity": 0.42,
        "confidence": 12.5,
        "user_id": "user2"
      },
      "error": null,
      "error_code": null
    }
  ],
  "message": "Batch verification completed: 2 successful, 0 failed"
}
```

## Error Scenarios

```
┌─────────────────────────────────────────────────────────────────┐
│  Scenario: Mismatched file/items count                          │
├─────────────────────────────────────────────────────────────────┤
│  Request: 3 files, 2 items                                       │
│  Response: {                                                     │
│    "total_items": 0,                                             │
│    "successful": 0,                                              │
│    "failed": 0,                                                  │
│    "message": "Files count (3) does not match items count (2)"  │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Scenario: Partial failures in batch                            │
├─────────────────────────────────────────────────────────────────┤
│  Request: 3 images (1 no face, 1 poor quality, 1 good)          │
│  Response: {                                                     │
│    "total_items": 3,                                             │
│    "successful": 1,                                              │
│    "failed": 2,                                                  │
│    "results": [                                                  │
│      {                                                           │
│        "status": "failed",                                       │
│        "error": "No face detected",                              │
│        "error_code": "NO_FACE_DETECTED"                          │
│      },                                                          │
│      {                                                           │
│        "status": "failed",                                       │
│        "error": "Quality check failed: score=65.2",              │
│        "error_code": "POOR_QUALITY"                              │
│      },                                                          │
│      {                                                           │
│        "status": "success",                                      │
│        "data": {...}                                             │
│      }                                                           │
│    ]                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Security Features

```
┌─────────────────────────────────────────────────────────────────┐
│                   SECURITY LAYERS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DoS Protection                                               │
│     ✓ Max batch size: 50 items                                  │
│     ✓ Max total file size: 50MB                                 │
│     ✓ Request timeout: 30s per operation                        │
│                                                                  │
│  2. Input Validation                                             │
│     ✓ File type validation (images only)                        │
│     ✓ JSON schema validation (Pydantic)                         │
│     ✓ File count = items count enforcement                      │
│                                                                  │
│  3. SQL Injection Prevention                                     │
│     ✓ Parameterized queries only                                │
│     ✓ No string concatenation in SQL                            │
│     ✓ Type-safe database operations                             │
│                                                                  │
│  4. Resource Management                                          │
│     ✓ Automatic temp file cleanup (finally blocks)              │
│     ✓ Connection pooling (prevents exhaustion)                  │
│     ✓ Async operations (non-blocking)                           │
│                                                                  │
│  5. Error Handling                                               │
│     ✓ No sensitive data in error messages                       │
│     ✓ Machine-readable error codes                              │
│     ✓ Graceful degradation (partial success)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

**Note:** All diagrams reflect the system state after applying the pgvector fix.
