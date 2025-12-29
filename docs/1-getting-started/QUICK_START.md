# Quick Start Guide

## Fastest Way to Test

### Option 1: Browser (Easiest!)
```
1. Open: http://localhost:8001/docs
2. Click any endpoint -> "Try it out"
3. Upload image and test!
```

### Option 2: Python Script
```bash
python test_complete_workflow.py
```

### Option 3: cURL
```bash
curl http://localhost:8001/api/v1/health
```

---

## Prerequisites

- Python 3.11+ installed
- Virtual environment activated
- Test images with clear, front-facing faces

---

## Start Server

```bash
# Activate virtual environment
# Linux/macOS
source venv/bin/activate

# Windows
.\.venv\Scripts\activate

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Server will be available at: **http://localhost:8001**

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/enroll` | POST | Enroll a face |
| `/api/v1/verify` | POST | Verify face (1:1) |
| `/api/v1/search` | POST | Search face (1:N) |
| `/api/v1/liveness` | POST | Liveness detection |
| `/api/v1/batch/enroll` | POST | Batch enrollment |
| `/api/v1/batch/verify` | POST | Batch verification |
| `/api/v1/card-type/detect-live` | POST | Card type detection |

---

## Run Tests

### Complete Workflow Test (Recommended)
```bash
python test_complete_workflow.py
```

**Tests:**
- Health check
- Enroll users
- Verify same person (should match)
- Verify different person (should NOT match)
- Liveness detection
- Error handling

### Find Good Images
```bash
python find_good_images.py
```

### Simple Interactive Test
```bash
python test_api_simple.py
```

---

## Interactive Testing (Browser)

### Swagger UI
**URL:** http://localhost:8001/docs

**How to use:**
1. Expand an endpoint (e.g., `/api/v1/enroll`)
2. Click "Try it out"
3. Fill in parameters:
   - `user_id`: "test_user_123"
   - `file`: Click "Choose File" and upload image
4. Click "Execute"
5. See response below

**Recommended order:**
1. GET `/api/v1/health` - Check server
2. POST `/api/v1/enroll` - Enroll a face
3. POST `/api/v1/verify` - Verify the same face
4. POST `/api/v1/liveness` - Check liveness

---

## Example Workflow

### 1. Health Check
```bash
curl http://localhost:8001/api/v1/health
```

### 2. Enroll User
```bash
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "user_id=john_doe" \
  -F "file=@/path/to/face.jpg"
```

### 3. Verify User
```bash
curl -X POST "http://localhost:8001/api/v1/verify" \
  -F "user_id=john_doe" \
  -F "file=@/path/to/another_face.jpg"
```

### 4. Check Liveness
```bash
curl -X POST "http://localhost:8001/api/v1/liveness" \
  -F "file=@/path/to/live_image.jpg"
```

---

## Expected Results

### Successful Enrollment
```json
{
  "success": true,
  "user_id": "john_doe",
  "quality_score": 85.5,
  "message": "Face enrolled successfully",
  "embedding_dimension": 128
}
```

### Successful Verification (Match)
```json
{
  "verified": true,
  "confidence": 0.87,
  "distance": 0.13,
  "threshold": 0.6,
  "message": "Face verified successfully"
}
```

### Failed Verification (Different Person)
```json
{
  "verified": false,
  "confidence": 0.05,
  "distance": 0.95,
  "threshold": 0.6,
  "message": "Face verification failed"
}
```

### Liveness Check Passed
```json
{
  "is_live": true,
  "liveness_score": 75.8,
  "challenge": "texture_analysis",
  "challenge_completed": true,
  "message": "Liveness check passed"
}
```

---

## Common Errors

### No Face Detected
```json
{
  "error_code": "FACE_NOT_DETECTED",
  "message": "No face detected in the image..."
}
```
**Solution:** Use image with clear, front-facing face

### Poor Quality
```json
{
  "error_code": "POOR_IMAGE_QUALITY",
  "message": "Image quality too low..."
}
```
**Solution:** Use higher quality image

### User Not Enrolled
```json
{
  "error_code": "EMBEDDING_NOT_FOUND",
  "message": "User not enrolled..."
}
```
**Solution:** Enroll user first before verification

---

## Troubleshooting

### Server not responding?
```bash
# Check if server is running
curl http://localhost:8001/api/v1/health

# If not, start it:
uvicorn app.main:app --reload --port 8001
```

### Image quality too low?
```bash
# Find images that work:
python find_good_images.py
```

---

## Documentation

- **API Documentation:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc
- **Full Testing Guide:** [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md)

---

## Quick Commands

```bash
# Start server
uvicorn app.main:app --reload --port 8001

# Test everything
python test_complete_workflow.py

# Find good images
python find_good_images.py

# Health check
curl http://localhost:8001/api/v1/health
```

---

## Tips for Best Results

### For Face Images:
- Front-facing face
- Good lighting
- Clear, not blurry
- Only one face in image
- Face size at least 80x80 pixels
- Avoid sunglasses, face masks, extreme angles
