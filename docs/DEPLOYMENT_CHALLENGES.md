# GCP Cloud Run Deployment Challenges

This document records the issues encountered during deployment to Google Cloud Platform Cloud Run on 2025-12-28.

## Summary

The deployment required **7 revision attempts** before succeeding. Each failure revealed a new dependency or compatibility issue that wasn't caught during local development.

## Issues Encountered (in order)

### 1. Missing libGL.so.1 (OpenGL Library)

**Error:**
```
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

**Cause:** OpenCV requires OpenGL libraries even when using `opencv-python-headless`.

**Fix:** Added `libgl1` to Dockerfile apt-get packages:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \  # <-- Added
    && rm -rf /var/lib/apt/lists/*
```

---

### 2. NumPy 2.x Incompatibility with TensorFlow 2.15

**Error:**
```
ImportError: numpy.core.umath failed to import
AttributeError: _UFUNC_API not found
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x
```

**Cause:**
- `requirements.txt` had `numpy>=1.26.0` which allowed numpy 2.x
- TensorFlow 2.15.0 was compiled against numpy 1.x and crashes with numpy 2.x
- Other packages (scikit-image, pandas) pulled in numpy 2.x as transitive dependency

**Fix:**
1. Updated `requirements.txt`: `numpy>=1.26.0,<2.0`
2. Created constraint file in Dockerfile to prevent any package from upgrading numpy:
```dockerfile
RUN echo "numpy<2.0" > /tmp/constraints.txt
RUN pip install --no-cache-dir -c /tmp/constraints.txt -r requirements.txt
```

---

### 3. Missing lightphe (DeepFace Dependency)

**Error:**
```
ModuleNotFoundError: No module named 'lightphe'
```

**Cause:** DeepFace was installed with `--no-deps` to avoid opencv-python conflicts, but this also skipped installing `lightphe` (homomorphic encryption library).

**Fix:** Explicitly install lightphe after deepface:
```dockerfile
RUN pip install --no-cache-dir --no-deps deepface>=0.0.79 && \
    pip install --no-cache-dir -c /tmp/constraints.txt lightphe
```

---

### 4. Keras 3.x Incompatibility with TensorFlow 2.15

**Error:**
```
ModuleNotFoundError: No module named 'tensorflow.keras'
```

**Cause:**
- `requirements.txt` had `keras>=2.2.0` which installed keras 3.x
- Keras 3.x is standalone and doesn't provide `tensorflow.keras` namespace
- TensorFlow 2.15 bundles Keras 2.15 internally
- DeepFace imports from `tensorflow.keras.models`

**Fix:**
1. Updated `requirements.txt`: `tf-keras>=2.15.0,<2.16.0`
2. Added keras constraint: `echo "keras<3.0" >> /tmp/constraints.txt`

---

### 5. Missing prometheus_client

**Error:**
```
ModuleNotFoundError: No module named 'prometheus_client'
```

**Cause:** The application uses Prometheus metrics for monitoring but the dependency wasn't in `requirements.txt`.

**Fix:** Added to `requirements.txt`:
```
prometheus_client>=0.17.0
```

---

## Root Causes Analysis

### Why These Issues Occurred

1. **Local vs Cloud Environment Mismatch**
   - Local Windows development with full GPU support
   - Cloud Run uses minimal Linux containers without GPU

2. **Transitive Dependency Hell**
   - ML packages have complex, interconnected dependencies
   - Version constraints weren't strict enough
   - `pip` doesn't prevent upgrades from transitive dependencies

3. **DeepFace Packaging Issues**
   - DeepFace depends on `opencv-python` (not headless)
   - Using `--no-deps` avoids opencv conflict but misses other deps

4. **Rapid Ecosystem Changes**
   - NumPy 2.0 released recently, breaking TensorFlow compatibility
   - Keras 3.0 separated from TensorFlow, changing import paths

---

## Lessons Learned

1. **Always use constraint files** for ML projects to lock critical packages
2. **Test container builds locally** before pushing to cloud
3. **Pin major versions** for numpy, keras, tensorflow together
4. **Document all implicit dependencies** that `--no-deps` skips
5. **Use slim base images carefully** - they may miss system libraries

---

## Recommended Dockerfile Pattern for ML Projects

```dockerfile
# Create constraints to prevent breaking upgrades
RUN echo "numpy<2.0" > /tmp/constraints.txt && \
    echo "keras<3.0" >> /tmp/constraints.txt

# Install in order: numpy first, then tensorflow, then others
RUN pip install -c /tmp/constraints.txt "numpy>=1.26.0,<2.0"
RUN pip install -c /tmp/constraints.txt tensorflow-cpu==2.15.0
RUN pip install -c /tmp/constraints.txt -r requirements.txt

# Always use constraints flag to prevent upgrades
```

---

## Final Working Configuration

- **Python:** 3.11-slim
- **TensorFlow:** 2.15.0 (CPU)
- **NumPy:** 1.26.x (< 2.0)
- **Keras:** Bundled with TF 2.15 (< 3.0)
- **OpenCV:** opencv-python-headless >= 4.8.0
- **DeepFace:** >= 0.0.79 (with lightphe)

## Time Impact

- Total deployment attempts: 7
- Estimated time lost: ~2-3 hours
- Each build+deploy cycle: ~15-20 minutes
