# CLAUDE.md - Biometric Processor

## Project Overview

Python 3.11+ / FastAPI biometric processing microservice for FIVUCSAS platform.
Handles face enrollment, verification, liveness detection, and document classification.
Clean Architecture with dependency injection.

## Build & Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Runs on port 8001. API docs at `/docs`. Demo UI served at root `/`.

## Run Tests

```bash
pytest                          # All tests
pytest --cov=app tests/         # With coverage
pytest tests/unit/ -v           # Unit tests only
```

## Key Directories

- `app/api/routes/` - API route handlers (17 modules)
- `app/domain/` - Domain entities and interfaces
- `app/application/use_cases/` - Business logic use cases
- `app/infrastructure/ml/` - ML model implementations (DeepFace, MediaPipe, YOLO)
- `app/infrastructure/persistence/` - Data repositories
- `app/core/` - Configuration and DI container

## Biometric Modality Support

### Fully implemented:
- **Face**: enroll, verify, search, liveness, quality, demographics, landmarks, comparison
- Routes: `enrollment.py`, `verification.py`, `search.py`, `liveness.py`, `quality.py`, etc.

### STUB only (always return failure):
- **Fingerprint**: `app/api/routes/fingerprint.py` - enroll/verify/delete endpoints exist but return `success: false`
- **Voice**: `app/api/routes/voice.py` - enroll/verify/delete endpoints exist but return `success: false`

### Not implemented:
- **Iris**: No endpoints at all

## Known Issues (March 2026)

### CRITICAL:
1. Fingerprint stubs cause identity-core-api FingerprintAuthHandler to always fail
2. Voice stubs cause identity-core-api VoiceAuthHandler to always fail
3. Only 5 of 20+ endpoint groups are consumed by other services

### Integration points:
- Called by **identity-core-api** (Java/Spring on port 8080) via BiometricServiceAdapter
- Called directly by **web-app** (React on port 3000) via BiometricService.ts for face operations

See TODO.md for full integration audit (18+ items).
