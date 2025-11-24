# Manual Testing Guide - Biometric Processor API

## Server Status ✅
**Server is running on:** http://localhost:8001

---

## Quick Start Methods

### 1. **Swagger UI (Easiest!)**
Open in your browser: **http://localhost:8001/docs**

This gives you a complete interactive interface where you can:
- ✅ See all endpoints
- ✅ Test requests directly
- ✅ Upload files
- ✅ View responses
- ✅ See request/response schemas

**Steps:**
1. Click on any endpoint to expand it
2. Click "Try it out"
3. Fill in parameters
4. Click "Execute"
5. See the response below

---

## 2. Test with cURL

### Health Check
```bash
curl http://localhost:8001/api/v1/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "model": "Facenet",
  "detector": "opencv"
}
```

### Root Endpoint
```bash
curl http://localhost:8001/
```

### Enroll Face
```bash
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "user_id=test_user_123" \
  -F "file=@C:/path/to/your/photo.jpg"
```

**Expected Response:**
```json
{
  "success": true,
  "user_id": "test_user_123",
  "quality_score": 85.5,
  "message": "Face enrolled successfully",
  "embedding_dimension": 128
}
```

### Verify Face (same person)
```bash
curl -X POST "http://localhost:8001/api/v1/verify" \
  -F "user_id=test_user_123" \
  -F "file=@C:/path/to/verify/photo.jpg"
```

**Expected Response:**
```json
{
  "verified": true,
  "confidence": 0.87,
  "distance": 0.13,
  "threshold": 0.6,
  "message": "Face verified successfully"
}
```

### Check Liveness
```bash
curl -X POST "http://localhost:8001/api/v1/liveness" \
  -F "file=@C:/path/to/live/photo.jpg"
```

**Expected Response:**
```json
{
  "is_live": true,
  "liveness_score": 75.8,
  "challenge": "none",
  "challenge_completed": true,
  "message": "Liveness check passed"
}
```

---

## 3. Test with PowerShell Script

Run the automated test:
```powershell
.\test_api.ps1
```

When prompted, enter a path to a test image with a face.

---

## 4. Test with PowerShell (Manual Commands)

### Health Check
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/health" -Method Get | ConvertTo-Json
```

### Root Endpoint
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/" -Method Get | ConvertTo-Json
```

### Enroll Face (PowerShell)
```powershell
$imagePath = "C:\path\to\your\photo.jpg"
$userId = "test_user_powershell"

# Read image
$imageBytes = [System.IO.File]::ReadAllBytes($imagePath)
$imageFileName = Split-Path $imagePath -Leaf

# Create form data
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"user_id`"$LF",
    $userId,
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"$imageFileName`"",
    "Content-Type: image/jpeg$LF"
) -join $LF

$bodyLines += $LF
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyLines)
$bodyBytes += $imageBytes
$bodyBytes += [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")

# Make request
$response = Invoke-RestMethod `
    -Uri "http://localhost:8001/api/v1/enroll" `
    -Method Post `
    -ContentType "multipart/form-data; boundary=$boundary" `
    -Body $bodyBytes

$response | ConvertTo-Json
```

---

## 5. Test with Python

### Install requests
```bash
pip install requests
```

### Test Script (test_manual.py)
```python
import requests
import json

BASE_URL = "http://localhost:8001/api/v1"

# 1. Health Check
print("Testing Health Endpoint...")
response = requests.get(f"{BASE_URL}/health")
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))
print()

# 2. Enroll Face
print("Testing Enrollment...")
with open("path/to/your/photo.jpg", "rb") as f:
    files = {"file": f}
    data = {"user_id": "test_user_python"}
    response = requests.post(f"{BASE_URL}/enroll", files=files, data=data)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()

# 3. Verify Face
print("Testing Verification...")
with open("path/to/verify/photo.jpg", "rb") as f:
    files = {"file": f}
    data = {"user_id": "test_user_python"}
    response = requests.post(f"{BASE_URL}/verify", files=files, data=data)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()

# 4. Liveness Check
print("Testing Liveness...")
with open("path/to/live/photo.jpg", "rb") as f:
    files = {"file": f}
    response = requests.post(f"{BASE_URL}/liveness", files=files)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
```

Run:
```bash
python test_manual.py
```

---

## 6. Test with JavaScript/Node.js

### Install axios
```bash
npm install axios form-data
```

### Test Script (test_manual.js)
```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const BASE_URL = 'http://localhost:8001/api/v1';

async function testAPI() {
    // 1. Health Check
    console.log('Testing Health Endpoint...');
    const health = await axios.get(`${BASE_URL}/health`);
    console.log('Status:', health.status);
    console.log(JSON.stringify(health.data, null, 2));
    console.log();

    // 2. Enroll Face
    console.log('Testing Enrollment...');
    const enrollForm = new FormData();
    enrollForm.append('user_id', 'test_user_nodejs');
    enrollForm.append('file', fs.createReadStream('path/to/your/photo.jpg'));
    
    const enroll = await axios.post(`${BASE_URL}/enroll`, enrollForm, {
        headers: enrollForm.getHeaders()
    });
    console.log('Status:', enroll.status);
    console.log(JSON.stringify(enroll.data, null, 2));
    console.log();

    // 3. Verify Face
    console.log('Testing Verification...');
    const verifyForm = new FormData();
    verifyForm.append('user_id', 'test_user_nodejs');
    verifyForm.append('file', fs.createReadStream('path/to/verify/photo.jpg'));
    
    const verify = await axios.post(`${BASE_URL}/verify`, verifyForm, {
        headers: verifyForm.getHeaders()
    });
    console.log('Status:', verify.status);
    console.log(JSON.stringify(verify.data, null, 2));
}

testAPI().catch(console.error);
```

Run:
```bash
node test_manual.js
```

---

## 7. Test with Browser DevTools

1. Open **http://localhost:8001/docs**
2. Open Browser DevTools (F12)
3. Go to **Network** tab
4. Execute requests in Swagger UI
5. Inspect HTTP requests/responses in Network tab

---

## Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root service info |
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/enroll` | Enroll a face |
| POST | `/api/v1/verify` | Verify a face (1:1) |
| POST | `/api/v1/liveness` | Check liveness |
| POST | `/api/v1/search` | Search for similar faces |
| POST | `/api/v1/batch/enroll` | Batch enrollment |

---

## Expected Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid input, no face detected, poor quality) |
| 404 | Not Found (user not enrolled) |
| 422 | Validation Error (missing/invalid parameters) |
| 500 | Internal Server Error |

---

## Common Test Scenarios

### ✅ Successful Enrollment
1. Use clear photo with one face
2. Good lighting
3. Face clearly visible
4. Returns 200 with embedding info

### ❌ Face Not Detected
1. Use photo without face
2. Returns 400 with "No face detected" message

### ❌ Poor Quality
1. Use blurry photo
2. Returns 400 with "Poor image quality" message

### ❌ Multiple Faces
1. Use photo with multiple faces
2. Returns 400 with "Multiple faces detected" message

### ✅ Successful Verification
1. Enroll a face first
2. Verify with same person's different photo
3. Returns 200 with verified=true

### ❌ User Not Enrolled
1. Try to verify without enrolling
2. Returns 404 with "User not enrolled" message

---

## Troubleshooting

### Server not responding?
- Check if server is running: `curl http://localhost:8001/`
- Check logs in the terminal where server is running

### 400 Bad Request?
- Check image file is valid JPEG/PNG
- Ensure face is clearly visible
- Check image quality (not too blurry)

### 422 Validation Error?
- Check required parameters are provided
- Verify parameter names are correct

### File upload fails?
- Check file path is correct
- Ensure file exists and is readable

---

## Tips for Best Results

### For Face Images:
- ✅ Front-facing face
- ✅ Good lighting
- ✅ Clear, not blurry
- ✅ Only one face in image
- ✅ Face size at least 80x80 pixels
- ❌ Avoid sunglasses
- ❌ Avoid face masks
- ❌ Avoid extreme angles

---

## Server Controls

### Start Server
```powershell
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Stop Server
Press `Ctrl+C` in the terminal

### View Logs
Logs appear in the terminal where server is running

---

## Links

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **OpenAPI JSON**: http://localhost:8001/openapi.json
- **Health Check**: http://localhost:8001/api/v1/health

---

**Happy Testing! 🧪**
