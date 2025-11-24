# Quick Start - Manual Testing Guide

## 🚀 Fastest Way to Test

### Option 1: Browser (Easiest!) ⭐
```
1. Open: http://localhost:8001/docs
2. Click any endpoint → "Try it out"
3. Upload image and test!
```

### Option 2: Python Script
```powershell
python test_complete_workflow.py
```

### Option 3: PowerShell Script
```powershell
.\test_api.ps1
```

---

## 📋 Prerequisites

✅ Server running on http://localhost:8001  
✅ Test images in: `C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images`

---

## 🎯 Start Server

```powershell
# Activate virtual environment
.\.venv\Scripts\activate

# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Server will be available at: **http://localhost:8001**

---

## 🧪 Run Tests

### Complete Workflow Test ⭐ Recommended
```powershell
python test_complete_workflow.py
```
**Tests:**
- Health check
- Enroll 3 users
- Verify same person (should match)
- Verify different person (should NOT match)
- Liveness detection
- Error handling

**Result:** Shows success rate and detailed results

### Find Good Images
```powershell
python find_good_images.py
```
**Purpose:** Identifies which images pass quality checks

### Simple Interactive Test
```powershell
python test_api_simple.py
```
**Purpose:** Step-by-step interactive testing

### PowerShell Test
```powershell
.\test_api.ps1
```
**Purpose:** Test with PowerShell, can specify image path

---

## 🌐 Interactive Testing (Browser)

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

## 📸 Good Test Images

Use these images (they pass quality checks):

```
person_0001\img_006.jpg  - Quality: 84.73
person_0002\img_008.jpg  - Quality: 88.68
person_0003\img_002.jpg  - Quality: 99.92
```

Full path:
```
C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images\person_0001\img_006.jpg
```

---

## 🎬 Example Workflow

### 1. Enroll User
```powershell
curl -X POST "http://localhost:8001/api/v1/enroll" `
  -F "user_id=john_doe" `
  -F "file=@C:\path\to\image.jpg"
```

### 2. Verify User
```powershell
curl -X POST "http://localhost:8001/api/v1/verify" `
  -F "user_id=john_doe" `
  -F "file=@C:\path\to\another_image.jpg"
```

### 3. Check Liveness
```powershell
curl -X POST "http://localhost:8001/api/v1/liveness" `
  -F "file=@C:\path\to\live_image.jpg"
```

---

## ✅ Expected Results

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

---

## ❌ Common Errors

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
  "message": "Image quality too low (score: 65/100, minimum: 70)..."
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

## 🔧 Troubleshooting

### Server not responding?
```powershell
# Check if server is running
curl http://localhost:8001/api/v1/health

# If not, start it:
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

### Image quality too low?
```powershell
# Find images that work:
python find_good_images.py
```

### Want to see what's working?
```powershell
# Run complete test:
python test_complete_workflow.py
```

---

## 📚 Documentation

- **Full Testing Guide:** [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md)
- **Test Results:** [MANUAL_TEST_RESULTS.md](MANUAL_TEST_RESULTS.md)
- **API Documentation:** http://localhost:8001/docs
- **Alternative Docs:** http://localhost:8001/redoc

---

## 🎯 Quick Commands

```powershell
# Start server
.\.venv\Scripts\activate && python -m uvicorn app.main:app --reload

# Test everything
python test_complete_workflow.py

# Find good images
python find_good_images.py

# Interactive test
python test_api_simple.py

# PowerShell test
.\test_api.ps1

# Health check
curl http://localhost:8001/api/v1/health
```

---

## 📊 Current Test Results

**Last Run:** 2025-11-20

- ✅ Health Check: **Working**
- ✅ Enrollment: **Working** (3/3 users)
- ✅ Same Person Verification: **100%** (3/3)
- ✅ Different Person Verification: **100%** (2/2)
- ✅ Liveness Detection: **Working** ✅

**Overall:** 🟢 **100% Success Rate** ✅

---

## 💡 Pro Tips

1. **Use Swagger UI** (http://localhost:8001/docs) for easiest testing
2. **Run `test_complete_workflow.py`** to verify everything works
3. **Check test results** in MANUAL_TEST_RESULTS.md
4. **Use good quality images** (find with `find_good_images.py`)
5. **Check server logs** if something fails

---

**Happy Testing! 🚀**
