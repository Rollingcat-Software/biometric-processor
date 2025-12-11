# New Features Design Document

**Date**: December 11, 2025
**Version**: 1.0
**Status**: Design Phase

---

## Overview

This document outlines the design for 11 new features to be added to the Biometric Processor API. All features follow Clean Architecture principles and existing patterns.

---

## Feature Summary

| # | Feature | Priority | Effort | Sprint |
|---|---------|----------|--------|--------|
| 1 | Face Quality Feedback | High | 1 day | 6.1 |
| 2 | Multi-face Detection | High | 1 day | 6.1 |
| 3 | Image Preprocessing | Medium | 2 days | 6.1 |
| 4 | Age/Gender Estimation | High | 2 days | 6.2 |
| 5 | Face Landmark Detection | Medium | 2 days | 6.2 |
| 6 | Anti-spoofing Report | High | 1 day | 6.2 |
| 7 | Similarity Matrix | Medium | 2 days | 6.3 |
| 8 | Face Comparison API | High | 2 days | 6.3 |
| 9 | Embedding Export/Import | Medium | 3 days | 6.3 |
| 10 | Webhook Notifications | Low | 3 days | 6.4 |
| 11 | Rate Limiting per Tenant | Low | 2 days | 6.4 |

---

## Architecture Overview

### New Directory Structure

```
app/
├── domain/
│   ├── entities/
│   │   ├── quality_feedback.py      # NEW
│   │   ├── multi_face_result.py     # NEW
│   │   ├── demographics.py          # NEW
│   │   ├── face_landmarks.py        # NEW
│   │   ├── liveness_report.py       # NEW
│   │   ├── similarity_matrix.py     # NEW
│   │   ├── face_comparison.py       # NEW
│   │   └── webhook_event.py         # NEW
│   ├── interfaces/
│   │   ├── demographics_analyzer.py # NEW
│   │   ├── landmark_detector.py     # NEW
│   │   ├── image_preprocessor.py    # NEW
│   │   └── webhook_sender.py        # NEW
│   └── exceptions/
│       └── webhook_errors.py        # NEW
├── application/
│   └── use_cases/
│       ├── analyze_quality.py       # NEW
│       ├── detect_multi_face.py     # NEW
│       ├── analyze_demographics.py  # NEW
│       ├── detect_landmarks.py      # NEW
│       ├── compare_faces.py         # NEW
│       ├── compute_similarity_matrix.py  # NEW
│       ├── export_embeddings.py     # NEW
│       ├── import_embeddings.py     # NEW
│       └── send_webhook.py          # NEW
├── infrastructure/
│   ├── ml/
│   │   ├── demographics/
│   │   │   └── deepface_demographics.py  # NEW
│   │   ├── landmarks/
│   │   │   └── mediapipe_landmarks.py    # NEW
│   │   └── preprocessing/
│   │       └── image_preprocessor.py     # NEW
│   └── webhooks/
│       └── http_webhook_sender.py   # NEW
├── api/
│   ├── routes/
│   │   ├── quality.py               # NEW
│   │   ├── multi_face.py            # NEW
│   │   ├── demographics.py          # NEW
│   │   ├── landmarks.py             # NEW
│   │   ├── comparison.py            # NEW
│   │   ├── similarity_matrix.py     # NEW
│   │   ├── embeddings_io.py         # NEW
│   │   └── webhooks.py              # NEW
│   └── schemas/
│       ├── quality.py               # NEW
│       ├── demographics.py          # NEW
│       ├── landmarks.py             # NEW
│       ├── comparison.py            # NEW
│       └── webhooks.py              # NEW
│   └── middleware/
│       └── rate_limiter.py          # UPDATE
└── core/
    └── config.py                    # UPDATE
```

---

## Feature 1: Face Quality Feedback

### Purpose
Return specific, actionable reasons why an image failed quality checks.

### API Endpoint

```
POST /api/v1/quality/analyze
```

### Request
```json
{
  "file": "<image_file>"
}
```

### Response
```json
{
  "overall_score": 72.5,
  "passed": false,
  "issues": [
    {
      "code": "BLUR_DETECTED",
      "severity": "high",
      "message": "Image is too blurry",
      "value": 45.2,
      "threshold": 100.0,
      "suggestion": "Use a stable camera or better lighting"
    },
    {
      "code": "FACE_TOO_SMALL",
      "severity": "medium",
      "message": "Face is too small in frame",
      "value": 65,
      "threshold": 80,
      "suggestion": "Move closer to the camera"
    }
  ],
  "metrics": {
    "blur_score": 45.2,
    "brightness": 0.65,
    "face_size": 65,
    "face_angle": 12.5,
    "occlusion": 0.0
  }
}
```

### Domain Entity

```python
# app/domain/entities/quality_feedback.py
@dataclass
class QualityIssue:
    code: str           # BLUR_DETECTED, FACE_TOO_SMALL, etc.
    severity: str       # high, medium, low
    message: str
    value: float
    threshold: float
    suggestion: str

@dataclass
class QualityMetrics:
    blur_score: float
    brightness: float
    face_size: int
    face_angle: float
    occlusion: float

@dataclass
class QualityFeedback:
    overall_score: float
    passed: bool
    issues: List[QualityIssue]
    metrics: QualityMetrics
```

### Issue Codes

| Code | Description | Threshold |
|------|-------------|-----------|
| `BLUR_DETECTED` | Image is blurry | blur_score < 100 |
| `LOW_BRIGHTNESS` | Image too dark | brightness < 0.3 |
| `HIGH_BRIGHTNESS` | Image too bright | brightness > 0.9 |
| `FACE_TOO_SMALL` | Face too small | face_size < 80px |
| `FACE_TOO_LARGE` | Face too close | face_size > 80% of image |
| `FACE_ANGLE` | Face not frontal | angle > 30° |
| `OCCLUSION` | Face partially covered | occlusion > 0.2 |
| `MULTIPLE_FACES` | Multiple faces detected | count > 1 |
| `NO_FACE` | No face detected | count = 0 |

---

## Feature 2: Multi-face Detection

### Purpose
Detect and return information about all faces in an image.

### API Endpoint

```
POST /api/v1/faces/detect-all
```

### Response
```json
{
  "face_count": 3,
  "faces": [
    {
      "face_id": 0,
      "bounding_box": {
        "x": 100, "y": 50, "width": 150, "height": 180
      },
      "confidence": 0.98,
      "quality_score": 85.5,
      "landmarks": {
        "left_eye": [125, 90],
        "right_eye": [175, 88],
        "nose": [150, 130],
        "mouth_left": [130, 160],
        "mouth_right": [170, 158]
      }
    },
    // ... more faces
  ],
  "image_dimensions": {
    "width": 1920,
    "height": 1080
  }
}
```

### Domain Entity

```python
# app/domain/entities/multi_face_result.py
@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

@dataclass
class BasicLandmarks:
    left_eye: Tuple[int, int]
    right_eye: Tuple[int, int]
    nose: Tuple[int, int]
    mouth_left: Tuple[int, int]
    mouth_right: Tuple[int, int]

@dataclass
class DetectedFace:
    face_id: int
    bounding_box: BoundingBox
    confidence: float
    quality_score: float
    landmarks: BasicLandmarks

@dataclass
class MultiFaceResult:
    face_count: int
    faces: List[DetectedFace]
    image_width: int
    image_height: int
```

---

## Feature 3: Image Preprocessing

### Purpose
Automatically preprocess images before face operations.

### Interface

```python
# app/domain/interfaces/image_preprocessor.py
class IImagePreprocessor(Protocol):
    def preprocess(
        self,
        image: np.ndarray,
        options: PreprocessOptions
    ) -> PreprocessResult:
        """Preprocess image for face recognition."""
        ...
```

### Preprocessing Steps

| Step | Description | Configurable |
|------|-------------|--------------|
| Auto-rotate | Fix EXIF orientation | Yes |
| Resize | Limit max dimension | Yes (max 1920px) |
| Normalize | Histogram equalization | Yes |
| Denoise | Remove noise | Yes |
| Color correction | White balance | Yes |

### Domain Entity

```python
# app/domain/entities/preprocess_result.py
@dataclass
class PreprocessOptions:
    auto_rotate: bool = True
    max_size: int = 1920
    normalize: bool = True
    denoise: bool = False
    color_correct: bool = False

@dataclass
class PreprocessResult:
    image: np.ndarray
    original_size: Tuple[int, int]
    new_size: Tuple[int, int]
    was_rotated: bool
    rotation_angle: int
    operations_applied: List[str]
```

---

## Feature 4: Age/Gender Estimation

### Purpose
Estimate age and gender from face image.

### API Endpoint

```
POST /api/v1/demographics/analyze
```

### Response
```json
{
  "age": {
    "value": 28,
    "range": [25, 32],
    "confidence": 0.85
  },
  "gender": {
    "value": "female",
    "confidence": 0.92
  },
  "race": {
    "dominant": "asian",
    "confidence": 0.78,
    "all": {
      "asian": 0.78,
      "white": 0.15,
      "black": 0.04,
      "indian": 0.02,
      "arab": 0.01
    }
  },
  "emotion": {
    "dominant": "happy",
    "confidence": 0.88,
    "all": {
      "happy": 0.88,
      "neutral": 0.08,
      "surprise": 0.02,
      "sad": 0.01,
      "angry": 0.01,
      "fear": 0.00,
      "disgust": 0.00
    }
  }
}
```

### Interface

```python
# app/domain/interfaces/demographics_analyzer.py
class IDemographicsAnalyzer(Protocol):
    def analyze(self, image: np.ndarray) -> DemographicsResult:
        """Analyze demographics from face image."""
        ...

    def get_supported_attributes(self) -> List[str]:
        """Get list of analyzable attributes."""
        ...
```

### Domain Entity

```python
# app/domain/entities/demographics.py
@dataclass
class AgeEstimate:
    value: int
    range: Tuple[int, int]
    confidence: float

@dataclass
class GenderEstimate:
    value: str  # "male" or "female"
    confidence: float

@dataclass
class RaceEstimate:
    dominant: str
    confidence: float
    all_probabilities: Dict[str, float]

@dataclass
class EmotionEstimate:
    dominant: str
    confidence: float
    all_probabilities: Dict[str, float]

@dataclass
class DemographicsResult:
    age: AgeEstimate
    gender: GenderEstimate
    race: Optional[RaceEstimate]
    emotion: Optional[EmotionEstimate]
```

### Implementation

Uses DeepFace's built-in `analyze()` function with actions=['age', 'gender', 'race', 'emotion'].

---

## Feature 5: Face Landmark Detection

### Purpose
Return detailed facial landmarks (68 or 468 points).

### API Endpoint

```
POST /api/v1/landmarks/detect
```

### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | string | "mediapipe" | Model: "dlib_68", "mediapipe_468" |
| `include_3d` | bool | false | Include 3D coordinates |

### Response
```json
{
  "model": "mediapipe_468",
  "landmark_count": 468,
  "landmarks": [
    {"id": 0, "x": 123, "y": 456, "z": 0.5},
    {"id": 1, "x": 125, "y": 458, "z": 0.48},
    // ... 468 points
  ],
  "regions": {
    "left_eye": [33, 133, 160, 159, 158, 144, 145, 153],
    "right_eye": [362, 263, 387, 386, 385, 373, 374, 380],
    "nose": [1, 2, 3, 4, 5, 6, 168, 197, 195, 5],
    "mouth": [61, 185, 40, 39, 37, 0, 267, 269, 270, 409],
    "left_eyebrow": [70, 63, 105, 66, 107, 55, 65],
    "right_eyebrow": [300, 293, 334, 296, 336, 285, 295],
    "face_oval": [10, 338, 297, 332, 284, 251, 389, 356, ...]
  },
  "face_mesh_connections": [...],  // For visualization
  "head_pose": {
    "pitch": 5.2,
    "yaw": -3.1,
    "roll": 1.8
  }
}
```

### Interface

```python
# app/domain/interfaces/landmark_detector.py
class ILandmarkDetector(Protocol):
    def detect(
        self,
        image: np.ndarray,
        include_3d: bool = False
    ) -> LandmarkResult:
        """Detect facial landmarks."""
        ...

    def get_landmark_count(self) -> int:
        """Get number of landmarks this detector provides."""
        ...
```

### Domain Entity

```python
# app/domain/entities/face_landmarks.py
@dataclass
class Landmark:
    id: int
    x: int
    y: int
    z: Optional[float] = None

@dataclass
class HeadPose:
    pitch: float  # Up/down
    yaw: float    # Left/right
    roll: float   # Tilt

@dataclass
class LandmarkResult:
    model: str
    landmark_count: int
    landmarks: List[Landmark]
    regions: Dict[str, List[int]]
    head_pose: Optional[HeadPose]
```

---

## Feature 6: Anti-spoofing Report

### Purpose
Provide detailed breakdown of liveness detection analysis.

### API Endpoint

```
POST /api/v1/liveness/report
```

### Response
```json
{
  "is_live": true,
  "overall_score": 78.5,
  "threshold": 70.0,
  "detection_mode": "combined",
  "analysis": {
    "passive": {
      "score": 72.3,
      "passed": true,
      "components": {
        "texture_analysis": {
          "score": 85.2,
          "weight": 0.35,
          "details": {
            "laplacian_variance": 245.6,
            "expected_range": [100, 500],
            "verdict": "Natural texture detected"
          }
        },
        "color_distribution": {
          "score": 68.4,
          "weight": 0.25,
          "details": {
            "hsv_variance": 0.42,
            "skin_tone_valid": true,
            "verdict": "Natural color distribution"
          }
        },
        "frequency_analysis": {
          "score": 71.0,
          "weight": 0.25,
          "details": {
            "high_freq_ratio": 0.38,
            "pattern_detected": false,
            "verdict": "No printing patterns"
          }
        },
        "moire_detection": {
          "score": 65.0,
          "weight": 0.15,
          "details": {
            "moire_score": 0.12,
            "screen_detected": false,
            "verdict": "No screen patterns"
          }
        }
      }
    },
    "active": {
      "score": 82.0,
      "passed": true,
      "components": {
        "eye_analysis": {
          "score": 90.0,
          "details": {
            "ear_value": 0.28,
            "ear_threshold": 0.25,
            "eyes_open": true,
            "blink_detected": false
          }
        },
        "mouth_analysis": {
          "score": 75.0,
          "details": {
            "mar_value": 0.45,
            "mar_threshold": 0.6,
            "smile_detected": false
          }
        }
      }
    }
  },
  "recommendations": [
    "Consider enabling active liveness for higher security",
    "Face angle is slightly off-center"
  ],
  "risk_level": "low"
}
```

### Domain Entity

```python
# app/domain/entities/liveness_report.py
@dataclass
class ComponentAnalysis:
    score: float
    weight: float
    details: Dict[str, Any]
    verdict: str

@dataclass
class PassiveAnalysis:
    score: float
    passed: bool
    texture: ComponentAnalysis
    color: ComponentAnalysis
    frequency: ComponentAnalysis
    moire: ComponentAnalysis

@dataclass
class ActiveAnalysis:
    score: float
    passed: bool
    eye_analysis: ComponentAnalysis
    mouth_analysis: ComponentAnalysis

@dataclass
class LivenessReport:
    is_live: bool
    overall_score: float
    threshold: float
    detection_mode: str
    passive: Optional[PassiveAnalysis]
    active: Optional[ActiveAnalysis]
    recommendations: List[str]
    risk_level: str  # low, medium, high
```

---

## Feature 7: Similarity Matrix

### Purpose
Compare multiple faces and return NxN similarity matrix.

### API Endpoint

```
POST /api/v1/similarity/matrix
```

### Request
```json
{
  "files": ["<image1>", "<image2>", "<image3>", ...],
  "labels": ["person_a", "person_b", "person_c", ...]  // Optional
}
```

### Response
```json
{
  "size": 3,
  "labels": ["person_a", "person_b", "person_c"],
  "matrix": [
    [1.00, 0.25, 0.18],
    [0.25, 1.00, 0.82],
    [0.18, 0.82, 1.00]
  ],
  "clusters": [
    {"cluster_id": 0, "members": ["person_a"]},
    {"cluster_id": 1, "members": ["person_b", "person_c"]}
  ],
  "pairs": [
    {"a": "person_a", "b": "person_b", "similarity": 0.25, "match": false},
    {"a": "person_a", "b": "person_c", "similarity": 0.18, "match": false},
    {"a": "person_b", "b": "person_c", "similarity": 0.82, "match": true}
  ],
  "threshold": 0.6,
  "computation_time_ms": 1250
}
```

### Domain Entity

```python
# app/domain/entities/similarity_matrix.py
@dataclass
class SimilarityPair:
    a: str
    b: str
    similarity: float
    match: bool

@dataclass
class Cluster:
    cluster_id: int
    members: List[str]

@dataclass
class SimilarityMatrixResult:
    size: int
    labels: List[str]
    matrix: List[List[float]]
    clusters: List[Cluster]
    pairs: List[SimilarityPair]
    threshold: float
    computation_time_ms: int
```

---

## Feature 8: Face Comparison API

### Purpose
Compare two face images directly without enrollment.

### API Endpoint

```
POST /api/v1/compare
```

### Request
```
Content-Type: multipart/form-data
- file1: <first_image>
- file2: <second_image>
- threshold: 0.6 (optional)
```

### Response
```json
{
  "match": true,
  "similarity": 0.87,
  "distance": 0.13,
  "threshold": 0.6,
  "confidence": "high",
  "face1": {
    "detected": true,
    "quality_score": 85.2,
    "bounding_box": {"x": 100, "y": 50, "width": 150, "height": 180}
  },
  "face2": {
    "detected": true,
    "quality_score": 82.8,
    "bounding_box": {"x": 120, "y": 60, "width": 140, "height": 170}
  },
  "message": "Faces match with high confidence"
}
```

### Domain Entity

```python
# app/domain/entities/face_comparison.py
@dataclass
class FaceInfo:
    detected: bool
    quality_score: float
    bounding_box: BoundingBox

@dataclass
class FaceComparisonResult:
    match: bool
    similarity: float
    distance: float
    threshold: float
    confidence: str  # high, medium, low
    face1: FaceInfo
    face2: FaceInfo
    message: str
```

---

## Feature 9: Embedding Export/Import

### Purpose
Export and import face embeddings for backup/migration.

### API Endpoints

```
GET  /api/v1/embeddings/export?tenant_id=default&format=json
POST /api/v1/embeddings/import
```

### Export Response
```json
{
  "version": "1.0",
  "export_date": "2025-12-11T10:30:00Z",
  "tenant_id": "default",
  "model": "Facenet",
  "embedding_dimension": 128,
  "count": 150,
  "embeddings": [
    {
      "user_id": "user_001",
      "embedding": [0.123, -0.456, ...],  // 128 floats
      "created_at": "2025-12-01T08:00:00Z",
      "metadata": {"name": "John Doe"}
    },
    // ...
  ],
  "checksum": "sha256:abc123..."
}
```

### Import Request
```json
{
  "file": "<export_file.json>",
  "mode": "merge",  // merge, replace, skip_existing
  "tenant_id": "default"
}
```

### Import Response
```json
{
  "success": true,
  "imported": 145,
  "skipped": 5,
  "errors": 0,
  "details": [
    {"user_id": "user_001", "status": "imported"},
    {"user_id": "user_002", "status": "skipped", "reason": "already_exists"}
  ]
}
```

---

## Feature 10: Webhook Notifications

### Purpose
Send async notifications on biometric events.

### Configuration

```python
# app/core/config.py additions
WEBHOOK_ENABLED: bool = False
WEBHOOK_URL: Optional[str] = None
WEBHOOK_SECRET: Optional[str] = None
WEBHOOK_EVENTS: List[str] = ["enrollment", "verification", "liveness"]
WEBHOOK_RETRY_COUNT: int = 3
WEBHOOK_TIMEOUT: int = 10
```

### API Endpoints

```
POST   /api/v1/webhooks/register
GET    /api/v1/webhooks
DELETE /api/v1/webhooks/{webhook_id}
POST   /api/v1/webhooks/{webhook_id}/test
```

### Webhook Payload

```json
{
  "event_id": "evt_abc123",
  "event_type": "enrollment.success",
  "timestamp": "2025-12-11T10:30:00Z",
  "tenant_id": "default",
  "data": {
    "user_id": "user_001",
    "quality_score": 85.5,
    "embedding_dimension": 128
  },
  "signature": "sha256=..."
}
```

### Event Types

| Event | Trigger |
|-------|---------|
| `enrollment.success` | Face enrolled successfully |
| `enrollment.failed` | Enrollment failed |
| `verification.match` | Face verified (match) |
| `verification.mismatch` | Face not matched |
| `liveness.pass` | Liveness check passed |
| `liveness.fail` | Liveness check failed |
| `search.found` | Face found in search |
| `search.not_found` | Face not found |

### Interface

```python
# app/domain/interfaces/webhook_sender.py
class IWebhookSender(Protocol):
    async def send(
        self,
        url: str,
        event: WebhookEvent,
        secret: Optional[str] = None
    ) -> WebhookResult:
        """Send webhook notification."""
        ...
```

### Domain Entity

```python
# app/domain/entities/webhook_event.py
@dataclass
class WebhookEvent:
    event_id: str
    event_type: str
    timestamp: datetime
    tenant_id: str
    data: Dict[str, Any]

@dataclass
class WebhookResult:
    success: bool
    status_code: Optional[int]
    response_time_ms: int
    error: Optional[str]
    retry_count: int
```

---

## Feature 11: Rate Limiting per Tenant

### Purpose
Apply different rate limits based on tenant/API key.

### Configuration

```python
# app/core/config.py additions
RATE_LIMIT_DEFAULT: int = 60  # requests per minute
RATE_LIMIT_PREMIUM: int = 300
RATE_LIMIT_STORAGE: str = "memory"  # memory, redis
```

### Rate Limit Tiers

| Tier | Requests/min | Burst |
|------|--------------|-------|
| Free | 60 | 10 |
| Standard | 120 | 20 |
| Premium | 300 | 50 |
| Unlimited | ∞ | ∞ |

### Response Headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1702296600
X-RateLimit-Tier: standard
```

### Rate Limit Exceeded Response

```json
{
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Try again in 45 seconds.",
  "retry_after": 45,
  "limit": 60,
  "tier": "standard"
}
```

### Implementation

```python
# app/api/middleware/rate_limiter.py
class TenantRateLimiter:
    def __init__(self, storage: IRateLimitStorage):
        self._storage = storage
        self._tiers = {
            "free": RateLimit(60, 10),
            "standard": RateLimit(120, 20),
            "premium": RateLimit(300, 50),
            "unlimited": RateLimit(float('inf'), float('inf'))
        }

    async def check(self, tenant_id: str, tier: str) -> RateLimitResult:
        """Check if request is within rate limit."""
        ...
```

---

## New API Endpoints Summary

| Endpoint | Method | Feature |
|----------|--------|---------|
| `/api/v1/quality/analyze` | POST | Quality Feedback |
| `/api/v1/faces/detect-all` | POST | Multi-face Detection |
| `/api/v1/demographics/analyze` | POST | Age/Gender |
| `/api/v1/landmarks/detect` | POST | Landmarks |
| `/api/v1/liveness/report` | POST | Anti-spoofing Report |
| `/api/v1/similarity/matrix` | POST | Similarity Matrix |
| `/api/v1/compare` | POST | Face Comparison |
| `/api/v1/embeddings/export` | GET | Export |
| `/api/v1/embeddings/import` | POST | Import |
| `/api/v1/webhooks` | GET/POST/DELETE | Webhooks |

---

## Configuration Additions

```python
# app/core/config.py additions

# Demographics
DEMOGRAPHICS_ENABLED: bool = True
DEMOGRAPHICS_INCLUDE_RACE: bool = False  # Privacy consideration
DEMOGRAPHICS_INCLUDE_EMOTION: bool = True

# Landmarks
LANDMARK_MODEL: Literal["dlib_68", "mediapipe_468"] = "mediapipe_468"

# Preprocessing
PREPROCESS_AUTO_ROTATE: bool = True
PREPROCESS_MAX_SIZE: int = 1920
PREPROCESS_NORMALIZE: bool = True

# Webhooks
WEBHOOK_ENABLED: bool = False
WEBHOOK_URL: Optional[str] = None
WEBHOOK_SECRET: Optional[str] = None
WEBHOOK_EVENTS: List[str] = ["enrollment", "verification", "liveness"]

# Rate Limiting
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_DEFAULT: int = 60
RATE_LIMIT_STORAGE: Literal["memory", "redis"] = "memory"

# Export/Import
EXPORT_FORMAT: Literal["json", "msgpack"] = "json"
EXPORT_INCLUDE_METADATA: bool = True
```

---

## Implementation Order

### Sprint 6.1 (Week 1)
1. Face Quality Feedback
2. Multi-face Detection
3. Image Preprocessing

### Sprint 6.2 (Week 2)
4. Age/Gender Estimation
5. Face Landmark Detection
6. Anti-spoofing Report

### Sprint 6.3 (Week 3)
7. Similarity Matrix
8. Face Comparison API
9. Embedding Export/Import

### Sprint 6.4 (Week 4)
10. Webhook Notifications
11. Rate Limiting per Tenant

---

## Dependencies to Add

```
# requirements.txt additions
scipy>=1.11.0          # For clustering in similarity matrix
httpx>=0.25.0          # For async webhook calls
msgpack>=1.0.0         # For binary export format (optional)
```

---

## Testing Strategy

Each feature requires:
1. Unit tests for domain entities
2. Unit tests for use cases
3. Integration tests for API endpoints
4. E2E workflow tests

Minimum coverage: 80%

---

## Documentation Updates

After implementation:
1. Update README.md with new endpoints
2. Update API documentation (Swagger)
3. Add examples for each new feature
4. Update QUICK_START.md

---

**Design Status**: COMPLETE
**Ready for Implementation**: YES
**Estimated Total Effort**: 4 weeks (1 sprint per week)
