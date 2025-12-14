# Biometric Processor API Documentation

**Version:** 1.0.0
**Base URL:** `http://localhost:8001/api/v1`

---

## Overview

The Biometric Processor API provides comprehensive face recognition and proctoring capabilities:

- **Face Enrollment** - Register face embeddings for users
- **Face Verification** - 1:1 matching against enrolled faces
- **Face Search** - 1:N search across all enrolled faces
- **Liveness Detection** - Anti-spoofing with active challenges
- **Batch Processing** - Async bulk operations
- **Real-time Proctoring** - Session monitoring with incident detection

---

## Authentication

All endpoints require authentication via API key:

```http
Authorization: Bearer <api_key>
X-Tenant-ID: <tenant_id>
```

---

## Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-12-12T12:00:00Z"
}
```

---

### Face Enrollment

```http
POST /enroll
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| image | file | Yes | Face image (JPEG/PNG) |
| user_id | string | Yes | Unique user identifier |
| tenant_id | string | No | Tenant identifier |

**Response:**
```json
{
  "enrollment_id": "uuid",
  "user_id": "user123",
  "quality_score": 0.92,
  "created_at": "2025-12-12T12:00:00Z"
}
```

---

### Face Verification

```http
POST /verify
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| image | file | Yes | Face image to verify |
| user_id | string | Yes | User ID to verify against |

**Response:**
```json
{
  "verified": true,
  "confidence": 0.95,
  "similarity_score": 0.87,
  "threshold": 0.6
}
```

---

### Liveness Detection

```http
POST /liveness
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| image | file | Yes | Face image for liveness check |

**Response:**
```json
{
  "is_live": true,
  "liveness_score": 85.5,
  "challenge": "smile_blink",
  "challenge_completed": true
}
```

---

### Face Search

```http
POST /search
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| image | file | Yes | Face image to search |
| max_results | int | No | Maximum results (default: 10) |
| threshold | float | No | Minimum similarity (default: 0.6) |

**Response:**
```json
{
  "results": [
    {
      "user_id": "user123",
      "similarity": 0.92,
      "enrollment_id": "uuid"
    }
  ]
}
```

---

## Proctoring API

### Create Session

```http
POST /proctor/sessions
Content-Type: application/json
```

**Request Body:**
```json
{
  "exam_id": "exam-001",
  "user_id": "user-123",
  "tenant_id": "tenant-abc",
  "config": {
    "gaze_threshold_seconds": 3.0,
    "risk_threshold": 0.7,
    "max_incidents": 10
  }
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "created",
  "created_at": "2025-12-12T12:00:00Z"
}
```

---

### Start Session

```http
POST /proctor/sessions/{session_id}/start
Content-Type: application/json
```

**Request Body:**
```json
{
  "baseline_image": "base64_encoded_image"
}
```

---

### Submit Frame

```http
POST /proctor/sessions/{session_id}/frames
Content-Type: application/json
```

**Request Body:**
```json
{
  "image": "base64_encoded_frame",
  "timestamp": "2025-12-12T12:00:00Z"
}
```

**Response:**
```json
{
  "frame_number": 100,
  "face_detected": true,
  "gaze_direction": "center",
  "risk_score": 0.15,
  "incidents": []
}
```

---

### WebSocket Streaming

```
WS /proctor/ws/{session_id}
```

Send binary frames directly for real-time processing.

**Message Format (JSON):**
```json
{
  "type": "frame",
  "data": "base64_frame",
  "timestamp": 1702389600000
}
```

---

### Get Session Status

```http
GET /proctor/sessions/{session_id}
```

**Response:**
```json
{
  "session_id": "uuid",
  "exam_id": "exam-001",
  "status": "started",
  "risk_score": 0.25,
  "incident_count": 2,
  "frame_count": 1500,
  "duration_seconds": 3600
}
```

---

### Get Incidents

```http
GET /proctor/sessions/{session_id}/incidents
```

**Response:**
```json
{
  "session_id": "uuid",
  "incidents": [
    {
      "id": "uuid",
      "type": "gaze_away_prolonged",
      "severity": "medium",
      "detected_at": "2025-12-12T12:30:00Z",
      "description": "Gaze away for 5.2 seconds"
    }
  ]
}
```

---

### End Session

```http
POST /proctor/sessions/{session_id}/end
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "completed",
  "summary": {
    "total_frames": 7200,
    "total_incidents": 3,
    "integrity_score": 0.85,
    "risk_level": "low"
  }
}
```

---

## Admin API

### Dashboard Metrics

```http
GET /api/admin/metrics/dashboard?period=24h
```

### System Health

```http
GET /api/admin/health
```

### List Sessions

```http
GET /api/admin/sessions?status=started&page=1&page_size=20
```

### Review Incident

```http
POST /api/admin/incidents/{incident_id}/review?action=confirm
```

---

## Error Handling

All errors return a standard format:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

| Code | HTTP Status | Description |
|------|-------------|-------------|
| FACE_NOT_DETECTED | 400 | No face found in image |
| MULTIPLE_FACES | 400 | Multiple faces detected |
| POOR_QUALITY | 400 | Image quality too low |
| NOT_FOUND | 404 | Resource not found |
| UNAUTHORIZED | 401 | Invalid or missing auth |
| RATE_LIMITED | 429 | Too many requests |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| /enroll | 100/min |
| /verify | 500/min |
| /search | 200/min |
| /liveness | 300/min |
| /proctor/frames | 60/sec |

---

## SDKs

- Python: `pip install biometric-processor-sdk`
- JavaScript: `npm install @biometric/processor`
- Go: `go get github.com/biometric/processor-go`
