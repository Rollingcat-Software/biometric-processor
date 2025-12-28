# GCP Cloud Run Deployment Challenges & Resolution

This document records the issues encountered during deployment to Google Cloud Platform Cloud Run on 2025-12-28, along with the infrastructure improvements implemented to prevent future issues.

## Executive Summary

The deployment required **7 revision attempts** before succeeding. Each failure revealed a new dependency or compatibility issue that wasn't caught during local development. After resolving deployment issues, we implemented comprehensive infrastructure improvements including CI/CD, monitoring, and database setup.

**Final Status: ✅ DEPLOYED AND OPERATIONAL**

---

## Part 1: Deployment Issues Encountered

### Issue 1: Missing libGL.so.1 (OpenGL Library)

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

### Issue 2: NumPy 2.x Incompatibility with TensorFlow 2.15

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

### Issue 3: Missing lightphe (DeepFace Dependency)

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

### Issue 4: Keras 3.x Incompatibility with TensorFlow 2.15

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

### Issue 5: Missing prometheus_client

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

### Issue 6: Database pgvector Extension Missing

**Error (post-deployment):**
```
Repository operation 'count' failed: unknown type: public.vector
```

**Cause:** The PostgreSQL database on Cloud SQL didn't have the pgvector extension enabled for vector similarity search.

**Fix:** Created a Cloud Run Job using postgres:15-alpine image to execute:
```sql
CREATE EXTENSION IF NOT EXISTS vector CASCADE;
```

**Command used:**
```bash
gcloud run jobs create db-init-job \
    --image=postgres:15-alpine \
    --command="psql" \
    --args="-c,CREATE EXTENSION IF NOT EXISTS vector CASCADE" \
    --set-cloudsql-instances=fivucsas:europe-west1:biometric-db \
    --set-env-vars="PGHOST=/cloudsql/fivucsas:europe-west1:biometric-db,PGUSER=postgres,PGPASSWORD=***,PGDATABASE=biometric"
```

---

## Part 2: Root Cause Analysis

### Why These Issues Occurred

1. **Local vs Cloud Environment Mismatch**
   - Local Windows development with full GPU support
   - Cloud Run uses minimal Linux containers without GPU
   - System libraries available locally but missing in slim containers

2. **Transitive Dependency Hell**
   - ML packages have complex, interconnected dependencies
   - Version constraints weren't strict enough
   - `pip` doesn't prevent upgrades from transitive dependencies
   - Package A requires numpy, Package B upgrades numpy, breaking Package A

3. **DeepFace Packaging Issues**
   - DeepFace depends on `opencv-python` (not headless)
   - Using `--no-deps` avoids opencv conflict but misses other deps
   - No clear documentation of all required dependencies

4. **Rapid Ecosystem Changes**
   - NumPy 2.0 released recently, breaking TensorFlow compatibility
   - Keras 3.0 separated from TensorFlow, changing import paths
   - These changes weren't communicated across package ecosystems

5. **Database Extension Not Pre-installed**
   - pgvector is not enabled by default on Cloud SQL
   - Application assumed extension was available
   - No migration/init step in deployment process

---

## Part 3: Infrastructure Improvements Implemented

### 3.1 Local Docker Build Test

Created scripts to catch build issues before pushing to GCP:

**Files:**
- `scripts/docker-build-test.sh` (Linux/Mac)
- `scripts/docker-build-test.ps1` (Windows)

**Usage:**
```bash
./scripts/docker-build-test.sh
```

This script:
1. Builds the Docker image locally
2. Starts a container
3. Waits for health check to pass
4. Reports success/failure before any cloud deployment

---

### 3.2 Locked Dependencies

Created `requirements-lock.txt` with all transitive dependencies pinned:

**Critical pins:**
```
numpy==1.26.4
keras==2.15.0
tensorflow-cpu==2.15.0
```

**Usage for production:**
```bash
pip install -r requirements-lock.txt
```

---

### 3.3 Health Check Monitoring

Set up Cloud Monitoring with uptime checks and alerts:

**Uptime Check:**
- Name: `Biometric-API-Health`
- Endpoint: `/api/v1/health`
- Frequency: Every 5 minutes
- Regions: Europe, USA-Iowa, Asia-Pacific

**Alert Policy:**
- Triggers when uptime check fails
- Auto-close after 7 days

**Commands used:**
```bash
gcloud monitoring uptime create "Biometric-API-Health" \
    --project=fivucsas \
    --resource-type=uptime-url \
    --resource-labels=host=biometric-api-902542798396.europe-west1.run.app,project_id=fivucsas \
    --protocol=https \
    --path="/api/v1/health" \
    --period=5 \
    --timeout=10 \
    --regions=europe,usa-iowa,asia-pacific
```

---

### 3.4 CI/CD Pipeline

Created GitHub Actions workflows:

**`.github/workflows/ci-cd.yml`:**
- Runs on push to main/dev
- Steps: Lint → Test → Docker Build → Deploy to Cloud Run
- Only deploys from main branch

**`.github/workflows/pr-validation.yml`:**
- Runs on pull requests
- Validates code formatting, linting, Docker build
- Runs security scans (safety, bandit)
- Comments results on PR

**Required GitHub Secrets:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

---

### 3.5 Database Initialization

Created database setup scripts and Cloud Run Job:

**Files:**
- `scripts/init-database.sql` - Full schema with pgvector
- `scripts/setup-database.md` - Manual setup instructions
- `scripts/db-init-job.py` - Python initialization script

**Cloud Run Job:**
```bash
gcloud run jobs execute db-init-job --region=europe-west1
```

---

## Part 4: Final Architecture

### GCP Resources

| Resource | Name | Region | Details |
|----------|------|--------|---------|
| Cloud Run | biometric-api | europe-west1 | 2 CPU, 2GB RAM |
| Cloud SQL | biometric-db | europe-west1 | PostgreSQL 15 + pgvector |
| Memorystore | biometric-cache | europe-west1 | Redis 7.0, 1GB |
| VPC Connector | biometric-connector | europe-west1 | Serverless VPC access |
| Uptime Check | Biometric-API-Health | Global | 5-min interval |

### Service URLs

- **API:** https://biometric-api-902542798396.europe-west1.run.app
- **Swagger Docs:** https://biometric-api-902542798396.europe-west1.run.app/docs
- **Health Check:** https://biometric-api-902542798396.europe-west1.run.app/api/v1/health

### Environment Variables (Cloud Run)

```
DATABASE_URL=postgresql://postgres:***@/biometric?host=/cloudsql/fivucsas:europe-west1:biometric-db
REDIS_URL=redis://10.210.16.3:6379
ENVIRONMENT=production
TF_CPP_MIN_LOG_LEVEL=2
DEEPFACE_HOME=/tmp/.deepface
```

---

## Part 5: Lessons Learned

### Technical Lessons

1. **Always use constraint files** for ML projects to lock critical packages
2. **Test container builds locally** before pushing to cloud
3. **Pin major versions** for numpy, keras, tensorflow together
4. **Document all implicit dependencies** that `--no-deps` skips
5. **Use slim base images carefully** - they may miss system libraries
6. **Include database migrations** in deployment process

### Process Lessons

1. **Each cloud deployment cycle takes 15-20 minutes** - test locally first
2. **Check Cloud Run logs immediately** after deployment failure
3. **Use Cloud Run Jobs** for one-time database operations
4. **Set up monitoring before** going to production
5. **Document everything** as you solve issues

---

## Part 6: Recommended Dockerfile Pattern

```dockerfile
FROM python:3.11-slim

# Install ALL required system libraries upfront
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Create constraints to prevent breaking upgrades
RUN echo "numpy<2.0" > /tmp/constraints.txt && \
    echo "keras<3.0" >> /tmp/constraints.txt

# Install in order: critical packages first
RUN pip install -c /tmp/constraints.txt "numpy>=1.26.0,<2.0"
RUN pip install -c /tmp/constraints.txt tensorflow-cpu==2.15.0
RUN pip install -c /tmp/constraints.txt opencv-python-headless>=4.8.0

# Install deepface without deps, then add missing ones
RUN pip install --no-deps deepface>=0.0.79 && \
    pip install -c /tmp/constraints.txt lightphe

# Install remaining requirements
RUN pip install -c /tmp/constraints.txt -r requirements.txt

# Verify everything works
RUN python -c "import cv2, numpy, tensorflow; print('All imports OK')"

COPY . .
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Part 7: Quick Reference Commands

### Deployment
```bash
# Deploy to Cloud Run
gcloud run deploy biometric-api --source=. --region=europe-west1

# Check service status
gcloud run services describe biometric-api --region=europe-west1

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=biometric-api" --limit=50
```

### Database
```bash
# Run DB init job
gcloud run jobs execute db-init-job --region=europe-west1 --wait

# Check Cloud SQL status
gcloud sql instances describe biometric-db
```

### Monitoring
```bash
# List uptime checks
gcloud monitoring uptime list-configs

# List alert policies
gcloud alpha monitoring policies list
```

---

## Time Impact Summary

| Phase | Time Spent | Attempts |
|-------|------------|----------|
| Initial deployment failures | ~2-3 hours | 7 revisions |
| Database setup (pgvector) | ~1 hour | Multiple job attempts |
| Infrastructure setup | ~1 hour | - |
| **Total** | **~4-5 hours** | - |

---

## Appendix: Files Created

```
scripts/
├── docker-build-test.sh      # Local Docker build test (bash)
├── docker-build-test.ps1     # Local Docker build test (PowerShell)
├── init-database.sql         # SQL initialization script
├── setup-database.md         # Database setup instructions
└── db-init-job.py           # Cloud Run Job for DB init

.github/workflows/
├── ci-cd.yml                # Main CI/CD pipeline
└── pr-validation.yml        # PR validation checks

infra/
├── monitoring-alert-policy.yaml
└── uptime-check.json

docs/
└── DEPLOYMENT_CHALLENGES.md  # This document

requirements-lock.txt         # Locked dependencies
Dockerfile.init              # DB initialization container
```

---

*Document last updated: 2025-12-28*
*Author: Claude Code (Automated)*
