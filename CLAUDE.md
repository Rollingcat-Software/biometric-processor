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
- **Voice**: enroll, verify, search, delete — Resemblyzer 256-dim speaker embeddings, centroid-based
- Routes: `voice.py`, repo: `pgvector_voice_repository.py`, embedder: `speaker_embedder.py`
- **Fingerprint**: enroll, verify, delete — SHA-256 hash-based 256-dim embeddings, centroid-based
- Routes: `fingerprint.py`, repo: `pgvector_fingerprint_repository.py`, embedder: `hash_embedder.py`

### Verification Pipeline (Phase 8B/8C, 2026-03-28):
- **Document scan** — YOLO-based document detection and classification
- **MRZ parser** — TD1/TD3 machine-readable zone extraction
- **Tesseract OCR** — TC Kimlik field extraction (name, TC number, DOB, photo)
- **Face-to-document matching** — DeepFace cosine similarity between selfie and document photo
- **Liveness pipeline** — server-authoritative liveness verdict with configurable thresholds
- **Video interview upload** — endpoint for verification pipeline video step
- Routes: `document.py`, `verification_pipeline.py`, `video_interview.py`

### Not implemented:
- **Iris**: No endpoints at all

## Known Issues (March 2026)

### CRITICAL:
1. Only 5 of 20+ endpoint groups are consumed by other services

### Integration points:
- Called by **identity-core-api** (Java/Spring on port 8080) via BiometricServiceAdapter
- Called directly by **web-app** (React on port 3000) via BiometricService.ts for face operations

See TODO.md for full integration audit (18+ items).
