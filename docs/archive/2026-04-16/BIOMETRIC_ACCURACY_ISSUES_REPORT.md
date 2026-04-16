# Biometric Processor - Accuracy Issues Investigation Report

**Date:** 2025-12-24
**Issue:** Biometric features (age, demographics) producing inaccurate results
**Example:** Senior (51 years old) detected as 30 years old

---

## Executive Summary

After comprehensive investigation of the biometric processor module, **multiple critical accuracy issues** have been identified across demographics analysis, configuration, and implementation. The primary issues stem from:

1. **Hardcoded fallback values** masking actual detection failures
2. **Poor model selection and configuration** for demographics analysis
3. **Image preprocessing problems** degrading input quality
4. **Known limitations of DeepFace library** for age estimation
5. **Missing validation and error handling**

---

## Critical Issues Identified

### 1. Demographics Analysis - Hardcoded Values (CRITICAL)

**Location:** `app/infrastructure/ml/demographics/deepface_demographics.py:80-85`

```python
# Extract age
age_value = int(results.get("age", 25))  # ⚠️ DEFAULT 25!
age = AgeEstimate(
    value=age_value,
    range=(max(0, age_value - 3), age_value + 4),  # ⚠️ Arbitrary range
    confidence=0.85,  # ⚠️ HARDCODED 85% confidence!
)
```

**Problems:**
- **Hardcoded default age of 25**: If DeepFace fails to return age, it silently defaults to 25 instead of reporting an error
- **Hardcoded confidence of 0.85 (85%)**: Completely ignores the actual model confidence, always reporting 85% confidence regardless of accuracy
- **Arbitrary age range**: The range of `(age-3, age+4)` has no scientific basis and doesn't reflect actual uncertainty
- **No error handling**: If age detection fails, the system lies to the user with fake confidence

**Impact:**
- Users receive inaccurate age predictions with false confidence scores
- No way to detect when the model is uncertain or failed
- Degrades trust in all biometric features

---

### 2. DeepFace Library - Known Age Estimation Issues

**Research Findings:**

According to recent studies and user reports:

- **Mean Absolute Error (MAE): 10.83 years** at optimal resolution (224x224 pixels)
- Users report extreme age predictions: "either 0 or 90+ most of the time"
- DeepFace's age estimation is **significantly less accurate** than alternatives like InsightFace (MAE: 7.46 years)
- Performance degrades dramatically with low-resolution or poor-quality images
- Pre-trained models may be biased toward certain age/gender distributions in training data

**Sources:**
- [DeepFace Age Prediction Issue #777](https://github.com/serengil/deepface/issues/777)
- [Impact of Image Resolution on Age Estimation (Nov 2024)](https://arxiv.org/html/2511.14689)

**Impact:**
- Age estimation can be off by 10+ years even under optimal conditions
- Your senior (51) being detected as 30 is a **21-year error**, which is within the realm of DeepFace's known poor performance

---

### 3. Image Preprocessing Issues

**Location:** `app/application/use_cases/analyze_demographics.py:56-61`

```python
# Extract face region
if detection_result.bounding_box:
    x, y, w, h = detection_result.bounding_box
    face_image = image[y : y + h, x : x + w]  # ⚠️ Crops and potentially degrades quality
else:
    face_image = image
```

**Problems:**
- **Face extraction before demographics analysis**: The system detects the face, crops it, then sends the cropped image to DeepFace.analyze()
- **No resolution validation**: Cropped face might be too small for accurate age estimation
- **Potential quality degradation**: Cropping can introduce artifacts or reduce resolution below the optimal 224x224 pixels
- **Double face detection**: DeepFace.analyze() will detect the face again internally, making the pre-cropping wasteful and potentially harmful

**Location:** `app/infrastructure/ml/demographics/deepface_demographics.py:68-73`

```python
results = DeepFace.analyze(
    img_path=image,
    actions=actions,
    enforce_detection=False,  # ⚠️ Will analyze even without proper face detection!
    silent=True,  # ⚠️ Hides warnings
)
```

**Problems:**
- **`enforce_detection=False`**: The system will attempt to analyze demographics even if no face is properly detected
- **`silent=True`**: Suppresses important warnings that could indicate quality issues
- **No image quality checks**: Doesn't verify resolution, brightness, or sharpness before analysis

**Impact:**
- Low-quality face regions produce even worse age estimates
- System silently processes bad images instead of rejecting them
- No feedback to improve image quality

---

### 4. Gender Estimation Issues

**Location:** `app/infrastructure/ml/demographics/deepface_demographics.py:88-98`

```python
gender_data = results.get("gender", {})
if isinstance(gender_data, dict):
    woman_conf = gender_data.get("Woman", 0)
    man_conf = gender_data.get("Man", 0)
    gender_value = "female" if woman_conf > man_conf else "male"
    gender_conf = max(woman_conf, man_conf) / 100.0
else:
    gender_value = str(gender_data).lower()
    gender_conf = 0.9  # ⚠️ Arbitrary fallback confidence
```

**Problems:**
- **Arbitrary fallback confidence of 0.9 (90%)**: If gender data isn't in expected format, assumes 90% confidence
- **No validation**: Doesn't check if confidence values are reasonable
- **Silent failures**: Falls back to string conversion without error reporting

**Impact:**
- Gender predictions may also have inflated confidence scores
- Failures are masked instead of reported

---

### 5. Configuration and Model Selection Issues

**No Environment Configuration:**
- No `.env` file exists in the repository
- All settings use defaults from code, which may not be optimal
- No way to tune thresholds or models without code changes

**Model Selection Issues:**
- `.env.example` shows `FACE_MODEL=VGG-Face` but code defaults to `Facenet`
- No configuration option to select different age/gender models
- DeepFace supports multiple backends but there's no way to select them for demographics

**Impact:**
- Users can't optimize model selection for their use case
- Can't A/B test different models to find better accuracy
- Stuck with suboptimal default configuration

---

### 6. Missing Validation and Error Handling

**Throughout the codebase:**

1. **No age range validation**: System accepts any age returned by DeepFace without sanity checks
2. **No confidence thresholding**: System returns results even with low confidence
3. **No input quality requirements**: Doesn't enforce minimum image resolution or quality
4. **No model warmup verification**: Doesn't verify demographics models loaded successfully
5. **Silent failure modes**: Uses `.get()` with defaults instead of failing fast

**Impact:**
- Garbage-in-garbage-out: Poor inputs produce poor outputs without warnings
- No way for users to know when results are unreliable
- System appears to work when it's actually failing

---

## Quality Assessment and Liveness Detection

### Quality Assessment - Status: ✅ ACCEPTABLE

The quality assessment implementation (`app/infrastructure/ml/quality/quality_assessor.py`) is well-designed:
- Proper blur detection using Laplacian variance
- Lighting assessment using brightness analysis
- Face size validation
- Weighted scoring system (blur: 40%, lighting: 30%, size: 30%)

**However:**
- Quality assessment is **not enforced** before demographics analysis
- Demographics analysis doesn't check if quality meets minimum thresholds

### Liveness Detection - Status: ✅ ACCEPTABLE

The liveness detection implementation is solid:
- Multiple detection methods (texture, color, frequency, moiré)
- Combined active + passive detection
- Proper weighting and thresholding
- Good error handling with fallbacks

**No critical issues found in liveness detection.**

---

## Root Cause Analysis

### Why is age detection so inaccurate?

The **51-year-old detected as 30** issue is caused by:

1. **DeepFace's inherent limitations**: MAE of ~10 years means errors of 20+ years are possible
2. **Hardcoded confidence masking failures**: System reports 85% confidence even when model is uncertain
3. **Image preprocessing degrading quality**: Cropping face before analysis reduces quality
4. **No quality validation**: Low-resolution or poor-quality images processed without rejection
5. **No error detection**: Silent fallback to default age of 25 when detection fails
6. **Suboptimal configuration**: Default settings not tuned for accuracy

---

## Recommended Fixes

### Priority 1: Fix Hardcoded Values (IMMEDIATE)

**File:** `app/infrastructure/ml/demographics/deepface_demographics.py`

```python
# BEFORE (WRONG):
age_value = int(results.get("age", 25))
age = AgeEstimate(
    value=age_value,
    range=(max(0, age_value - 3), age_value + 4),
    confidence=0.85,
)

# AFTER (CORRECT):
# Extract age with validation
if "age" not in results:
    raise DemographicsError("Age estimation failed - no age returned by model")

age_value = int(results["age"])

# Validate age is reasonable
if not (0 <= age_value <= 120):
    raise DemographicsError(f"Invalid age detected: {age_value}")

# Calculate proper confidence based on model uncertainty
# DeepFace doesn't return age confidence directly, so we estimate based on range
age_std = results.get("age_std", 10.0)  # Standard deviation if available
confidence = max(0.3, min(0.95, 1.0 - (age_std / 30.0)))  # Lower std = higher confidence

# Use realistic age range based on known model uncertainty (~±10 years)
age_range_margin = max(5, int(age_std * 1.5)) if age_std else 10
age = AgeEstimate(
    value=age_value,
    range=(max(0, age_value - age_range_margin), min(120, age_value + age_range_margin)),
    confidence=confidence,
)
```

### Priority 2: Remove Face Cropping Before Demographics

**File:** `app/application/use_cases/analyze_demographics.py`

```python
# BEFORE (WRONG):
detection_result = await self._detector.detect(image)
if detection_result.bounding_box:
    x, y, w, h = detection_result.bounding_box
    face_image = image[y : y + h, x : x + w]  # ❌ Don't crop!
else:
    face_image = image

# AFTER (CORRECT):
# DeepFace.analyze handles face detection internally - don't pre-crop!
# Just validate that a face exists
detection_result = await self._detector.detect(image)
if not detection_result.found:
    raise FaceNotFoundError("No face detected in image")

# Send full image to demographics analyzer - it will detect and analyze properly
result = self._demographics_analyzer.analyze(image)
```

### Priority 3: Add Quality Validation

**File:** `app/infrastructure/ml/demographics/deepface_demographics.py`

```python
def analyze(self, image: np.ndarray) -> DemographicsResult:
    # Validate image quality before analysis
    h, w = image.shape[:2]
    if min(h, w) < 224:
        raise DemographicsError(
            f"Image too small for accurate demographics: {w}x{h}. "
            f"Minimum recommended: 224x224 pixels"
        )

    # Enable detection enforcement and warnings
    results = DeepFace.analyze(
        img_path=image,
        actions=actions,
        enforce_detection=True,  # ✅ Fail if no face detected
        silent=False,  # ✅ Show warnings
    )
```

### Priority 4: Add Confidence Thresholding

**File:** `app/infrastructure/ml/demographics/deepface_demographics.py`

```python
# After extracting demographics, validate confidence
MIN_CONFIDENCE_THRESHOLD = 0.5  # Configurable

if age.confidence < MIN_CONFIDENCE_THRESHOLD:
    logger.warning(
        f"Low age estimation confidence: {age.confidence:.2f}. "
        f"Result may be unreliable."
    )
    # Either reject or add warning flag

if gender.confidence < MIN_CONFIDENCE_THRESHOLD:
    logger.warning(
        f"Low gender estimation confidence: {gender.confidence:.2f}. "
        f"Result may be unreliable."
    )
```

### Priority 5: Consider Alternative Libraries

Given DeepFace's poor age estimation performance (MAE: 10.83 years), consider:

1. **InsightFace**: Better age estimation accuracy (MAE: 7.46 years)
2. **FairFace**: Focuses on age/gender/race with better fairness
3. **AgeGenderEstimator**: Specialized for age/gender only

**Implementation:**
- Add abstraction layer for demographics analyzer
- Support multiple backends (DeepFace, InsightFace, FairFace)
- Allow configuration selection via environment variable

### Priority 6: Add Configuration Options

**File:** `app/core/config.py` (additions)

```python
# Demographics Model Selection
DEMOGRAPHICS_BACKEND: Literal["deepface", "insightface", "fairface"] = Field(default="deepface")
DEMOGRAPHICS_MIN_CONFIDENCE: float = Field(default=0.5, ge=0.0, le=1.0)
DEMOGRAPHICS_MIN_IMAGE_SIZE: int = Field(default=224, ge=128, le=1024)
DEMOGRAPHICS_AGE_MARGIN: int = Field(default=10, ge=5, le=20)
```

---

## Testing Recommendations

1. **Create age estimation test suite:**
   - Test with known-age faces across age ranges (20s, 30s, 40s, 50s, 60s+)
   - Measure actual MAE (Mean Absolute Error)
   - Compare against InsightFace or other alternatives

2. **Image quality testing:**
   - Test with various resolutions (128x128, 224x224, 512x512)
   - Test with various lighting conditions
   - Test with motion blur, compression artifacts

3. **Confidence calibration:**
   - Measure correlation between reported confidence and actual accuracy
   - Adjust confidence thresholds based on real performance

4. **Edge case testing:**
   - Very young faces (< 18)
   - Elderly faces (> 65)
   - Partial occlusions (glasses, masks, beards)
   - Different ethnicities and genders

---

## Conclusion

The biometric processor has **multiple critical accuracy issues** primarily in the demographics analysis module:

1. **Hardcoded values** (age=25, confidence=0.85) completely undermine result reliability
2. **DeepFace library limitations** (MAE ~10 years) mean even optimal implementation will have errors
3. **Image preprocessing** degrades quality before analysis
4. **Missing validation** allows poor-quality inputs to produce garbage outputs
5. **No error handling** silently fails instead of alerting users

**Immediate Actions Required:**
1. Fix hardcoded values in demographics analyzer (Priority 1)
2. Remove face cropping before demographics analysis (Priority 2)
3. Add quality validation and confidence thresholding (Priority 3-4)
4. Consider switching to more accurate libraries like InsightFace (Priority 5)

**Long-term Actions:**
1. Add comprehensive testing suite
2. Add configuration options for model selection
3. Implement confidence-based result rejection
4. Add telemetry to track real-world accuracy

---

## Sources

- [DeepFace Age Prediction Issues - GitHub Issue #777](https://github.com/serengil/deepface/issues/777)
- [Impact of Image Resolution on Age Estimation with DeepFace and InsightFace - ArXiv Nov 2024](https://arxiv.org/html/2511.14689)
- [DeepFace Age Analysis Discussion - GitHub Issue #125](https://github.com/serengil/deepface/issues/125)
- [DeepFace Age Probabilities Feature Request - GitHub Issue #1448](https://github.com/serengil/deepface/issues/1448)
