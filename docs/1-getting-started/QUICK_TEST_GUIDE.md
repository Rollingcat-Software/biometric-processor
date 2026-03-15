# Quick Test Guide for Deployed API

> **Note:** The GCP Cloud Run deployment (`biometric-api-902542798396.europe-west1.run.app`) is no longer active. The biometric-processor now runs locally via WSL2 and is exposed via Cloudflare Tunnel at `https://bpa-fivucsas.rollingcatsoftware.com`. Replace all URLs below with the Cloudflare Tunnel URL when the tunnel is running, or `http://localhost:8001` for local testing.

Since you have access to the deployed API at:
**https://bpa-fivucsas.rollingcatsoftware.com** (or `http://localhost:8001` locally)

Here are quick tests you can run from your browser or terminal.

---

## Method 1: Browser Testing

### Test Health Endpoint (Easiest!)

Just open this URL in your browser:
```
https://biometric-api-902542798396.europe-west1.run.app/api/v1/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "FIVUCSAS Biometric Processor",
  "version": "1.0.0",
  "model": "Facenet"
}
```

### View API Documentation

Open in browser:
```
https://biometric-api-902542798396.europe-west1.run.app/docs
```

This gives you an **interactive Swagger UI** where you can test all endpoints directly!

---

## Method 2: Terminal Testing (curl)

### 1. Health Check
```bash
curl https://biometric-api-902542798396.europe-west1.run.app/api/v1/health
```

### 2. Quality Analysis (with test image)
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/quality/analyze \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg"
```

### 3. Face Detection
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/face/detect \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg"
```

### 4. Demographics Analysis
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/demographics/analyze \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg"
```

### 5. Liveness Check
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/liveness/check \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg"
```

### 6. Facial Landmarks
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/landmarks/detect \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg"
```

### 7. Enroll a Face
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/enroll \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg" \
  -F "user_id=test-user-001" \
  -F "tenant_id=test-tenant"
```

### 8. Verify a Face
```bash
# First enroll (see above), then verify with different photo
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/verify \
  -F "file=@tests/fixtures/images/afuat/3.jpg" \
  -F "user_id=test-user-001" \
  -F "tenant_id=test-tenant"
```

### 9. Search for a Face
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/search \
  -F "file=@tests/fixtures/images/afuat/3.jpg" \
  -F "tenant_id=test-tenant" \
  -F "max_results=5"
```

### 10. Compare Two Faces
```bash
curl -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/compare \
  -F "file1=@tests/fixtures/images/afuat/profileImage_1200.jpg" \
  -F "file2=@tests/fixtures/images/afuat/3.jpg"
```

---

## Method 3: Comprehensive Automated Testing

Run the Python test suite (from your machine):

```bash
# Update the test script to use deployed URL (already done in test_deployed_api.py)
python test_deployed_api.py
```

This will:
- Test all 35 test cases
- Generate `DEPLOYED_API_TEST_REPORT.md`
- Show pass/fail for each endpoint
- Measure response times
- Provide detailed error analysis

**Expected Duration:** 2-3 minutes

---

## Method 4: Interactive Testing (Postman/Insomnia)

1. Import the OpenAPI spec from:
   ```
   https://biometric-api-902542798396.europe-west1.run.app/openapi.json
   ```

2. Test endpoints interactively with:
   - Request history
   - Environment variables
   - Response validation

---

## What to Look For

### ✅ Success Indicators

1. **Health Endpoint**: Returns 200 with `"status": "healthy"`
2. **Quality Analysis**: Returns 0-100 scores (NOT 2000+%)
3. **Demographics**:
   - Good images → 200 with age/gender/emotion
   - Small images (<224px) → 400 Bad Request (NOT 500!)
4. **Face Detection**: Returns bounding box and confidence
5. **Enrollment**: Returns 200 with embedding_id
6. **Verification**: Returns match boolean and similarity score

### ⚠️ Issues to Report

1. **500 Internal Server Error** on any endpoint
2. **Quality scores > 100%** (should be fixed!)
3. **Blur scores > 100%** (should be fixed!)
4. **Demographics returning 500 for small images** (should be 400!)
5. **Any crashes or timeouts**

---

## Test Images Available

From the repository:

```
tests/fixtures/images/
├── afuat/
│   ├── profileImage_1200.jpg  ← Good quality, large
│   ├── 3.jpg                  ← Small image (test demographics 400 error)
│   ├── DSC_8681.jpg           ← No face (test error handling)
│   └── indir.jpg              ← Tiny face
├── aga/
│   ├── spring21_veda1.png     ← Good PNG
│   └── indir.jpg              ← Small face
└── ahab/
    ├── foto.jpg               ← Different person
    └── 1679744618228.jpg      ← Same person, different photo
```

---

## Quick One-Liner Tests

### Test All Core Endpoints Quickly
```bash
# Health
curl -s https://biometric-api-902542798396.europe-west1.run.app/api/v1/health | jq

# Quality (normalized scores check)
curl -s -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/quality/analyze \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg" | jq '.overall_score'

# Demographics (should work with good image)
curl -s -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/demographics/analyze \
  -F "file=@tests/fixtures/images/afuat/profileImage_1200.jpg" | jq '.age'

# Demographics (should return 400 for small image, NOT 500!)
curl -s -X POST https://biometric-api-902542798396.europe-west1.run.app/api/v1/demographics/analyze \
  -F "file=@tests/fixtures/images/afuat/3.jpg" | jq '.error_code'
```

---

## Expected Response Times

| Endpoint | Expected Response Time |
|----------|------------------------|
| `/health` | < 100ms |
| `/quality/analyze` | 200-500ms |
| `/demographics/analyze` | 1-3s (ML inference) |
| `/face/detect` | 100-300ms |
| `/landmarks/detect` | 300-800ms |
| `/liveness/check` | 500-1500ms |
| `/enroll` | 300-800ms |
| `/verify` | 400-1000ms |
| `/search` | 500-2000ms |
| `/compare` | 600-1200ms |

---

## Troubleshooting

### If you get 403 Forbidden
- The proxy might be blocking your IP
- Try from a different network or VPN

### If you get 500 Internal Server Error
- Check GCP Cloud Run logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision" --limit=50
  ```

### If you get 502 Bad Gateway
- Service might be cold-starting (wait 30s and retry)
- Or deployment might have failed

### If demographics returns 500 for small images
- This is the bug we're verifying!
- Should return 400 with clear error message
- Report this if it still happens

---

## After Testing

### Report Results

Create an issue or update the test report with:
1. Which endpoints passed/failed
2. Any unexpected errors (especially 500s)
3. Response times (slow endpoints)
4. Whether bug fixes are working:
   - Quality scores normalized (0-100)?
   - Demographics returns 400 for small images?
   - Live camera working?

### Next Steps

Once all tests pass:
1. Update `COMPREHENSIVE_STATUS_AND_TEST_REPORT.md` with results
2. Set deployment confidence to 95/100
3. Plan production rollout
4. Create monitoring dashboards
5. Document any performance issues

---

**Happy Testing! 🚀**

*For comprehensive automated testing, use: `python test_deployed_api.py`*
