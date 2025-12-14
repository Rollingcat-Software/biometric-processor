# Biometric Processor API Test Plan

## Test Data
- **Location**: `D:\Kişisel\Bitirme\img`
- **Persons**:
  - `afuat`: 10 images (various qualities)
  - `aga`: 7 images
  - `ahab`: 2 images (high quality)

## Test Categories

### 1. Health Check
- [ ] GET /api/v1/health - Basic health check

### 2. Enrollment Tests
- [ ] Enroll user with valid image
- [ ] Enroll same user again (update)
- [ ] Enroll with different tenant_id
- [ ] Enroll with low quality image
- [ ] Enroll with no face image
- [ ] Enroll with multiple faces image
- [ ] Enroll with invalid file type

### 3. Verification Tests (1:1)
- [ ] Verify enrolled user with same image
- [ ] Verify enrolled user with different image (same person)
- [ ] Verify enrolled user with different person's image
- [ ] Verify non-existent user
- [ ] Verify with wrong tenant_id
- [ ] Verify with no face image

### 4. Search Tests (1:N)
- [ ] Search with enrolled person's image
- [ ] Search with non-enrolled person's image
- [ ] Search with different thresholds
- [ ] Search with max_results limit
- [ ] Search with tenant_id filter

### 5. Liveness Detection Tests
- [ ] Liveness check with real photo
- [ ] Liveness check with various image qualities

### 6. Quality Analysis Tests
- [ ] Analyze high quality image
- [ ] Analyze low quality/blurry image
- [ ] Analyze small face image
- [ ] Analyze image with no face

### 7. Demographics Tests
- [ ] Analyze age/gender/emotion
- [ ] Test with different faces

### 8. Face Comparison Tests
- [ ] Compare same person (different images)
- [ ] Compare different persons
- [ ] Compare with threshold parameter

### 9. Multi-face Detection Tests
- [ ] Detect single face
- [ ] Test max_faces parameter

### 10. Batch Operations Tests
- [ ] Batch enroll multiple users
- [ ] Batch verify multiple users

### 11. Embeddings Export/Import Tests
- [ ] Export embeddings
- [ ] Import embeddings

### 12. Webhook Tests
- [ ] Register webhook
- [ ] List webhooks
- [ ] Delete webhook

### 13. Admin Tests
- [ ] Get system stats
- [ ] Get recent activity

---

## Issues Found

| # | Endpoint | Issue | Severity | Status |
|---|----------|-------|----------|--------|
| | | | | |

