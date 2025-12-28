# Liveness Detection Implementation Guide

A practical guide for implementing and improving liveness detection in the Biometric Processor system.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current Implementation](#2-current-implementation)
3. [API Reference](#3-api-reference)
4. [Detection Methods](#4-detection-methods)
5. [Frontend Integration](#5-frontend-integration)
6. [Configuration & Tuning](#6-configuration--tuning)
7. [Attack Types & Detection](#7-attack-types--detection)
8. [Future: Active Liveness (Puzzle System)](#8-future-active-liveness-puzzle-system)
9. [Testing & Validation](#9-testing--validation)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Overview

### Current Approach: Hybrid Liveness Detection

The system uses a **combined liveness detector** that merges:

| Method | Type | Weight | Description |
|--------|------|--------|-------------|
| **Texture Analysis** | Passive | 40% | Detects printed photos, screen displays |
| **Facial Landmarks** | Active | 60% | Analyzes natural facial features via MediaPipe |

### Detection Flow

```
Image Upload → Face Detection → Face Crop → Liveness Analysis → Result
                                    ↓
                         ┌─────────────────────┐
                         │  Texture Detector   │ → texture, color, frequency, moire scores
                         └─────────────────────┘
                                    +
                         ┌─────────────────────┐
                         │  Active Detector    │ → landmarks, EAR, MAR scores
                         └─────────────────────┘
                                    ↓
                              Combined Score
```

---

## 2. Current Implementation

### Backend Components

| Component | Location | Description |
|-----------|----------|-------------|
| `TextureLivenessDetector` | `app/infrastructure/ml/liveness/texture_liveness_detector.py` | Passive texture analysis |
| `ActiveLivenessDetector` | `app/infrastructure/ml/liveness/active_liveness_detector.py` | MediaPipe landmark analysis |
| `CombinedLivenessDetector` | `app/infrastructure/ml/liveness/combined_liveness_detector.py` | Merges both methods |
| `CheckLivenessUseCase` | `app/application/use_cases/check_liveness.py` | Orchestrates the flow |

### Processing Pipeline

1. **Image Loading** - Read uploaded image via OpenCV
2. **Face Detection** - Locate face and get bounding box
3. **Face Cropping** - Crop to face region with 40% padding (improves accuracy)
4. **Liveness Analysis** - Run texture + active detectors
5. **Score Combination** - Weighted average of both scores
6. **Decision** - Compare against threshold, return result

---

## 3. API Reference

### Current Endpoint

```
POST /api/v1/liveness
Content-Type: multipart/form-data
```

#### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Face image (JPEG/PNG) |

#### Response

```json
{
  "is_live": true,
  "liveness_score": 78.5,
  "challenge": "combined",
  "challenge_completed": true,
  "message": "Liveness check passed - live person detected",
  "checks": [
    {
      "name": "texture",
      "passed": true,
      "score": 72.0,
      "details": "Moderate texture variance"
    },
    {
      "name": "color",
      "passed": true,
      "score": 85.0,
      "details": "Natural color distribution"
    },
    {
      "name": "frequency",
      "passed": true,
      "score": 80.0,
      "details": "No print patterns detected"
    },
    {
      "name": "moire",
      "passed": true,
      "score": 90.0,
      "details": "No screen patterns detected"
    },
    {
      "name": "face_landmarks",
      "passed": true,
      "score": 85.0,
      "details": "Face landmarks detected"
    },
    {
      "name": "natural_features",
      "passed": true,
      "score": 85.0,
      "details": "Natural facial features detected"
    }
  ],
  "spoof_type": null,
  "processing_time_ms": 245.3
}
```

#### Spoof Types

| Type | Description |
|------|-------------|
| `screen_replay` | Screen/monitor display detected (moire patterns) |
| `printed_photo` | Printed photo detected (texture/frequency analysis) |
| `digital_manipulation` | Unnatural color distribution |
| `static_image` | No natural facial features detected |
| `suspected_spoof` | Generic low score |

---

## 4. Detection Methods

### 4.1 Texture Analysis (Laplacian Variance)

Detects printed photos by analyzing texture variation.

```python
# Real faces have more texture variation than printed photos
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
laplacian = cv2.Laplacian(gray, cv2.CV_64F)
variance = laplacian.var()
```

**Score Mapping:**
| Variance | Score | Interpretation |
|----------|-------|----------------|
| < 20 | 0-30 | Likely printed/very smooth |
| 20-50 | 30-60 | Suspicious |
| 50-150 | 60-85 | Normal webcam range |
| > 150 | 85-100 | High detail |

### 4.2 Color Analysis (HSV Distribution)

Detects screens and prints via unnatural color distributions.

```python
hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
saturation = hsv[:, :, 1]
sat_mean = np.mean(saturation)

value = hsv[:, :, 2]
val_std = np.std(value)
```

**Ideal Ranges:**
- Saturation mean: ~80 (moderate)
- Value std: ~50 (good brightness variation)

### 4.3 Frequency Analysis (FFT)

Detects printing patterns via frequency domain analysis.

```python
f_transform = np.fft.fft2(gray)
f_shift = np.fft.fftshift(f_transform)
magnitude = np.abs(f_shift)

# Compare high vs low frequency content
freq_ratio = high_freq_mean / low_freq_mean
```

### 4.4 Moiré Detection (Gabor Filters)

Detects screen displays via moiré pattern detection.

```python
for theta in [0, π/4, π/2, 3π/4]:
    kernel = cv2.getGaborKernel(
        ksize=(15, 15),
        sigma=3.0,
        theta=theta,
        lambd=6.0,  # Small wavelength for high-frequency patterns
        gamma=0.5,
        psi=0
    )
    filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
```

### 4.5 Facial Landmark Analysis (MediaPipe)

Analyzes natural facial features using 468 landmarks.

**Key Metrics:**

#### Eye Aspect Ratio (EAR)
```
EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
```

**MediaPipe Landmark Indices:**
```python
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
```

| EAR Value | Interpretation |
|-----------|----------------|
| 0.25 - 0.35 | Normal open eyes |
| 0.15 - 0.25 | Partially closed |
| < 0.15 | Closed/blinking |

#### Mouth Aspect Ratio (MAR)
```
MAR = vertical_distance / horizontal_distance
```

**MediaPipe Landmark Indices:**
```python
MOUTH_CORNER_LEFT = 61
MOUTH_CORNER_RIGHT = 291
UPPER_LIP_CENTER = 13
LOWER_LIP_CENTER = 14
```

| MAR Value | Interpretation |
|-----------|----------------|
| 0.2 - 0.5 | Neutral expression |
| 0.5 - 0.8 | Slight smile |
| > 0.8 | Wide smile/open mouth |

---

## 5. Frontend Integration

### 5.1 Camera Setup with Face Guide

```tsx
// WebcamCapture component with oval guide
<div className="relative">
  <video ref={videoRef} autoPlay playsInline muted />

  {/* Face positioning overlay */}
  <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
    <defs>
      <mask id="faceMask">
        <rect width="100" height="100" fill="white" />
        <ellipse cx="50" cy="42" rx="24" ry="32" fill="black" />
      </mask>
    </defs>
    <rect fill="rgba(0,0,0,0.5)" mask="url(#faceMask)" />
    <ellipse cx="50" cy="42" rx="24" ry="32"
             fill="none" stroke="white" strokeWidth="0.5" />
  </svg>
</div>
```

### 5.2 Image Capture Best Practices

```typescript
// Capture with high quality for better liveness detection
canvas.toBlob(
  (blob) => { /* handle blob */ },
  'image/jpeg',
  0.95  // High quality reduces compression artifacts
);
```

### 5.3 API Integration

```typescript
async function checkLiveness(image: File | Blob): Promise<LivenessResponse> {
  const formData = new FormData();

  if (image instanceof Blob && !(image instanceof File)) {
    formData.append('file', image, 'capture.jpg');
  } else {
    formData.append('file', image);
  }

  const response = await fetch('/api/v1/liveness', {
    method: 'POST',
    body: formData,
  });

  return response.json();
}
```

### 5.4 UX Guidelines

| Guideline | Implementation |
|-----------|----------------|
| **Face positioning** | Show oval guide overlay |
| **Lighting feedback** | Warn if image too dark/bright |
| **Distance guidance** | "Move closer" / "Move back" hints |
| **Clear instructions** | "Position your face within the oval" |
| **Quick feedback** | Show result within 500ms |

---

## 6. Configuration & Tuning

### 6.1 Threshold Reference

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `liveness_threshold` | 65.0 | 0-100 | Overall pass/fail threshold |
| `texture_threshold` | 60.0 | 0-100 | Texture detector threshold |
| `active_threshold` | 70.0 | 0-100 | Active detector threshold |
| `texture_weight` | 0.4 | 0-1 | Weight for texture score |
| `active_weight` | 0.6 | 0-1 | Weight for active score |
| `ear_threshold` | 0.25 | 0-1 | Eye open/closed boundary |
| `mar_threshold` | 0.6 | 0-1 | Smile detection boundary |

### 6.2 Tuning for Different Scenarios

**High Security (Banking, Government)**
```python
liveness_threshold = 75.0
texture_threshold = 70.0
active_threshold = 75.0
```

**Standard Security (General apps)**
```python
liveness_threshold = 65.0
texture_threshold = 60.0
active_threshold = 70.0
```

**Low Friction (Consumer apps)**
```python
liveness_threshold = 55.0
texture_threshold = 50.0
active_threshold = 60.0
```

### 6.3 Per-Check Pass Threshold

Individual checks must score ≥ 50 to pass. Liveness requires:
- Combined score ≥ threshold
- Minimum 2-3 checks passing

---

## 7. Attack Types & Detection

### 7.1 Attack Matrix

| Attack Type | Detection Method | Key Indicators |
|-------------|------------------|----------------|
| **Printed Photo** | Texture + Frequency | Low variance, print patterns |
| **Screen Replay** | Moiré + Color | Moiré patterns, unnatural colors |
| **Static Image** | Active Landmarks | No natural facial proportions |
| **Deepfake Video** | Background + Texture | Background inconsistency |
| **3D Mask** | Texture + Color | Unusual texture, color distribution |

### 7.2 Detection Accuracy Targets

| Metric | Target | Description |
|--------|--------|-------------|
| **True Accept Rate** | > 95% | Real users pass correctly |
| **Spoof Rejection Rate** | > 99% | Attacks correctly blocked |
| **False Reject Rate** | < 5% | Real users wrongly rejected |
| **Processing Time** | < 300ms | End-to-end API response |

---

## 8. Future: Active Liveness (Puzzle System)

### 8.1 Proposed Endpoints

```
POST /api/v1/liveness/generate-puzzle
POST /api/v1/liveness/verify
```

### 8.2 Puzzle Flow

```
1. Client requests puzzle
2. Server returns random action sequence
3. Client guides user through actions
4. Client detects actions locally (MediaPipe)
5. Client submits evidence + final frame
6. Server validates and returns result
```

### 8.3 Supported Actions

| Action | Detection | Threshold |
|--------|-----------|-----------|
| `blink` | EAR dip + recovery | EAR < 0.20 then > 0.25 |
| `blink_left` | Left EAR only | Left EAR < 0.20 |
| `blink_right` | Right EAR only | Right EAR < 0.20 |
| `smile` | MAR increase | MAR > 0.6 for 5+ frames |
| `look_left` | Yaw angle | Yaw > 15° |
| `look_right` | Yaw angle | Yaw < -15° |
| `look_up` | Pitch angle | Pitch < -10° |
| `look_down` | Pitch angle | Pitch > 10° |

### 8.4 State Machine

```
IDLE → PERMISSION_REQUESTED → CAMERA_READY → PUZZLE_LOADING
                                                    ↓
SUCCESS ← VERIFYING_BACKEND ← STEP_PASSED ← STEP_RUNNING
    ↓                              ↑            ↓
  DONE                         (next step)   FAILED
```

---

## 9. Testing & Validation

### 9.1 Test Dataset Requirements

| Category | Count | Description |
|----------|-------|-------------|
| Real faces | 100+ | Various lighting, angles, ethnicities |
| Printed photos | 50+ | Different print qualities |
| Screen replays | 50+ | Phone, tablet, monitor |
| Static images | 30+ | Digital photos displayed |

### 9.2 Unit Test Examples

```python
# Test texture score calculation
def test_texture_score_real_face():
    image = load_test_image("real_face.jpg")
    score = detector._calculate_texture_score(image)
    assert score >= 60.0  # Real faces should score high

def test_texture_score_printed():
    image = load_test_image("printed_photo.jpg")
    score = detector._calculate_texture_score(image)
    assert score < 50.0  # Printed should score low
```

### 9.3 Integration Test

```python
async def test_liveness_endpoint():
    with open("test_face.jpg", "rb") as f:
        response = await client.post(
            "/api/v1/liveness",
            files={"file": ("test.jpg", f, "image/jpeg")}
        )

    assert response.status_code == 200
    data = response.json()
    assert "is_live" in data
    assert "liveness_score" in data
    assert "checks" in data
```

---

## 10. Troubleshooting

### 10.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| False rejections | Low quality webcam | Increase lighting, use higher resolution |
| Slow processing | Large image size | Resize before upload (max 1920px) |
| "No face detected" | Face not centered | Show positioning guide |
| Inconsistent scores | Compression artifacts | Use JPEG quality 0.9+ |
| MediaPipe errors | Missing dependencies | Install `mediapipe` package |

### 10.2 Debug Logging

Enable detailed logging:
```python
import logging
logging.getLogger("app.infrastructure.ml.liveness").setLevel(logging.DEBUG)
```

Log output includes:
- Individual check scores
- Combined score calculation
- Spoof type determination
- Processing time breakdown

### 10.3 Image Quality Checklist

- [ ] Face clearly visible (not blurry)
- [ ] Good lighting (not too dark/bright)
- [ ] Face centered in frame
- [ ] Single face only
- [ ] Minimal compression artifacts
- [ ] Resolution ≥ 640x480

---

## Appendix A: MediaPipe Landmark Reference

### Face Mesh Indices (468 total)

```
Eyes:
  Left:  [362, 385, 387, 263, 373, 380]
  Right: [33, 160, 158, 133, 153, 144]

Mouth:
  Left corner:  61
  Right corner: 291
  Upper lip:    13
  Lower lip:    14

Nose:
  Tip: 4

Face contour:
  [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
   397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
   172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
```

---

## Appendix B: Score Calculation Summary

### Combined Score Formula

```
combined_score = (texture_score × 0.4) + (active_score × 0.6)

is_live = (combined_score >= threshold) AND (passed_checks >= min_checks)
```

### Texture Score Components

```
texture_score =
    (texture × 0.35) +
    (color × 0.25) +
    (frequency × 0.25) +
    (moire × 0.15)
```

### Active Score Components

```
active_score =
    30 (base: landmarks detected) +
    35 (eyes open) +
    15 (natural EAR range) +
    20 (natural facial proportions) +
    5  (smile bonus, optional)
```
