# Batch Processing Endpoints Testing Guide

## Quick Fix for Current Issue

### Problem
Batch endpoints fail with: `invalid input for query argument $3: [...] (expected str, got list)`

### Solution (2 steps)

**Step 1: Install pgvector package**
```bash
pip install pgvector>=0.2.4
```

**Step 2: Update `app/infrastructure/persistence/repositories/pgvector_embedding_repository.py`**

Find the `_setup_connection` method (around line 147) and update it:

```python
async def _setup_connection(self, conn: asyncpg.Connection) -> None:
    """Setup connection configuration for pgvector."""
    from pgvector.asyncpg import register_vector

    # Register vector type for pgvector extension
    # This ensures vectors are properly handled by asyncpg
    await register_vector(conn)  # ADD THIS LINE
    await conn.execute("SET statement_timeout = '30s'")
    logger.debug(f"Configured connection {id(conn)} for pgvector")
```

**Step 3: Restart the API server**
```bash
# Stop the server (Ctrl+C)
# Then restart
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Quick Test Commands

### Test 1: Single Enrollment
```bash
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "file=@tests/fixtures/images/afuat/504494494_4335957489965886_7910713263520300979_n.jpg" \
  -F "user_id=test_afuat"
```

### Test 2: Batch Enroll (3 images for Afuat)
```bash
curl -X POST "http://localhost:8001/api/v1/batch/enroll" \
  -F "files=@tests/fixtures/images/afuat/profileImage_1200.jpg" \
  -F "files=@tests/fixtures/images/afuat/indir.jpg" \
  -F "files=@tests/fixtures/images/afuat/h02.jpg" \
  -F 'items=[{"user_id":"afuat_batch"},{"user_id":"afuat_batch"},{"user_id":"afuat_batch"}]' \
  -F "skip_duplicates=false"
```

### Test 3: Batch Verify
```bash
# First enroll if not already done
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "file=@tests/fixtures/images/aga/h03.jpg" \
  -F "user_id=aga_verify_test"

# Then verify with batch
curl -X POST "http://localhost:8001/api/v1/batch/verify" \
  -F "files=@tests/fixtures/images/aga/DSC_8476.jpg" \
  -F "files=@tests/fixtures/images/aga/indir.jpg" \
  -F 'items=[{"item_id":"v1","user_id":"aga_verify_test"},{"item_id":"v2","user_id":"aga_verify_test"}]' \
  -F "threshold=0.6"
```

## Available Test Images

- **Afuat**: 10 images in `tests/fixtures/images/afuat/`
- **Aga**: 7 images in `tests/fixtures/images/aga/`
- **Ahab**: 2 images in `tests/fixtures/images/ahab/`

## Endpoint Documentation

### POST /api/v1/batch/enroll

Enroll multiple face images in a single request.

**Parameters:**
- `files` (required): List of image files
- `items` (required): JSON array of `{"user_id": "...", "tenant_id": "..."}` objects
- `skip_duplicates` (optional, default=true): Skip users that already exist

**Response:**
```json
{
  "total_items": 3,
  "successful": 3,
  "failed": 0,
  "skipped": 0,
  "results": [
    {
      "item_id": "user1",
      "status": "success",
      "data": {"enrollment_id": "uuid", "quality_score": 85.5},
      "error": null,
      "error_code": null
    }
  ],
  "message": "Batch enrollment completed: 3 successful, 0 failed, 0 skipped"
}
```

**Limits:**
- Max 50 images per batch
- Max 50MB total file size

### POST /api/v1/batch/verify

Verify multiple faces against enrolled users.

**Parameters:**
- `files` (required): List of image files
- `items` (required): JSON array of `{"item_id": "...", "user_id": "...", "tenant_id": "..."}` objects
- `threshold` (optional, default=0.6): Similarity threshold (0.0-2.0)

**Response:**
```json
{
  "total_items": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "item_id": "verify1",
      "status": "success",
      "data": {"matched": true, "similarity": 0.85, "confidence": 95.2},
      "error": null,
      "error_code": null
    }
  ],
  "message": "Batch verification completed: 2 successful, 0 failed"
}
```

## Error Codes

- `NO_FACE_DETECTED`: No face found in image
- `POOR_QUALITY`: Image quality below threshold
- `USER_NOT_FOUND`: User not enrolled (verification only)
- `REPOSITORY_ERROR`: Database operation failed
- `UNKNOWN_ERROR`: Other errors

## Performance Tips

1. **Batch vs Individual**: Batch requests save HTTP overhead and can be 30-50% faster
2. **Optimal Batch Size**: 5-20 images per batch for best balance
3. **Image Quality**: Higher quality images = faster processing + better accuracy
4. **Concurrent Batches**: API supports multiple concurrent batch requests

## Common Issues

### Issue: "Files count does not match items count"
**Solution**: Ensure array lengths match: `files.length === items.length`

### Issue: "Invalid items JSON"
**Solution**: Check JSON syntax, use proper quotes: `'items=[{"user_id":"test"}]'`

### Issue: "Batch size exceeds maximum"
**Solution**: Split into smaller batches (max 50 items)

### Issue: "No face detected"
**Solution**: Use higher quality images with clear, frontal faces

## Full Test Suite

See `test_batch_results.md` for comprehensive test scenarios including:
- Single person batches
- Multi-person batches
- Error handling tests
- Performance comparisons
- Skip duplicates behavior
- Cross-person verification tests
