# CLAUDE.md - Biometric Processor

## Project Overview

Python 3.12 / FastAPI biometric processing microservice for FIVUCSAS platform.
Handles face enrollment, verification, liveness detection, and document classification.
Clean Architecture with dependency injection.

## Build & Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## ⚠️ Rebuild caution — dependency lock (2026-05-29)

The deployed prod image (`75347c98…`, healthy) is ~2 weeks old. `requirements.txt`
historically pinned everything with `>=`, so a fresh rebuild drifted ~42 packages
(numpy 2.4.4→2.4.6, protobuf 7.34.1→7.35.0, uniface 3.6.0→3.7.0, fastapi, nvidia-*, …).
The drifted set **segfaults** during the UniFace MiniFASNet ONNX session preload at
full-app boot under the `read_only` rootfs + `cap_drop:ALL` runtime (a native-ABI
interaction — an isolated MiniFASNet load works in BOTH uniface versions, so it's the
combination, not one library). Two other rebuild blockers were already fixed in
`docker-compose.prod.yml` (cap_add CHOWN/SETUID/SETGID for the gosu drop; forward the
DeepFace SHA pin from .env.prod).

**UPDATE 2026-05-29 (verified in isolation):** pinning `numpy==2.4.4` + `uniface==3.6.0`
to the exact working versions is **NOT sufficient** — a from-scratch rebuild STILL
segfaults at the MiniFASNet ONNX load. The remaining cause is base-image + deeper
native drift: the floating `python:3.12-slim` base moved **Debian 13.4→13.5**
(glibc deb13u2→u3) and torch/nvidia-cu13/onnxruntime-transitive libs drifted. So the
canonical `Dockerfile` cannot currently be rebuilt for prod.

**WHAT IS DEPLOYED NOW:** the prod image is built via **`Dockerfile.liveness-overlay`** —
a code-only layer `FROM` the proven working image (`75347c98`, retagged
`biometric-processor-biometric-api:working-75347c98`) that overlays the current `app/`
source (incl. liveness-on-enroll #119) onto the exact known-good dependency set. This
ships the security feature with zero dep-drift risk. `ENROLL_LIVENESS_ENABLED=True`.
To redeploy a code change: `docker build -f Dockerfile.liveness-overlay -t
biometric-processor-biometric-api:latest . && docker compose -f docker-compose.prod.yml
--env-file .env.prod up -d biometric-api` (boot-test first; roll back by retagging
`working-75347c98` → `:latest`).

**STILL TODO (tracked — reproducible canonical build):** pin the base image by DIGEST
(both `FROM` lines) to a known-good build + install from
`requirements-known-good-2026-05-29.lock` (handling the tf-cpu/deepface/opencv
special-casing so the lock's `tensorflow` line doesn't pull the GPU wheel). Until then
the overlay is the deploy path. The `requirements.txt` native pins + the compose
cap_add/DeepFace-env fixes remain in place as partial groundwork.

## Migrations (Alembic)

Alembic is included in `requirements.txt` and `Dockerfile.gpu` since PR #68
(2026-05-02 morning) — `alembic upgrade head` runs inside the runtime
container. The earlier manual-SQL workaround for embedding-ciphertext
backfill (Task #81) is obsolete; `backfill_embedding_ciphertext.py` was
also repaired in the same PR.

Runs on port 8001. API docs at `/docs`. Demo UI served at root `/` (disabled in production).

## Security (Production)

- **Internal only**: No public Traefik route. bio.fivucsas.com is NOT publicly accessible.
- **API key required**: `SimpleAPIKeyMiddleware` enforces `X-API-Key` header on all `/api/*` routes.
- **Demo UI disabled**: `DEMO_UI_ENABLED=false` in production `.env.prod`.
- **Network access**: Only reachable via Docker `proxy`/`backend` networks by identity-core-api.
- **Caller**: identity-core-api passes API key via `BiometricProcessorClient` using `BIOMETRIC_SERVICE_API_KEY` env var.

## Run Tests

```bash
pytest                          # All tests
pytest --cov=app tests/         # With coverage
pytest tests/unit/ -v           # Unit tests only
```

### Test/CI honesty (P2-2, 2026-05-30)

The CI unit + integration jobs no longer carry any `--ignore` flags. Two
mechanisms keep the suite honestly green without hiding broken files:

1. **Lazy DeepFace import.** `deepface_detector.py`, `deepface_extractor.py`
   and `deepface_demographics.py` now `import DeepFace` lazily (inside the
   methods that call it) instead of at module top. DeepFace pulls in
   TensorFlow, which is NOT in the lint/unit CI image, so this lets `app.main`
   and `DeepFaceDetector` import without TF. `test_deepface_detector.py` runs
   its pure post-filter geometry in CI; its single TF-dependent assertion is
   `@pytest.mark.skipif(not _TF_AVAILABLE)` (runs only inside the Docker ML
   stack).

2. **Env-gated full-stack integration.** The five integration files that used
   to be silently `--ignore`d now COLLECT cleanly (the module-scoped TestClient
   pattern no longer breaks collection because `app.main` imports without TF).
   The subset that genuinely needs the live ML + persistence stack is
   module/class-gated:
   - `RUN_FULL_STACK_INTEGRATION=true` → `test_api_routes.py`,
     `test_critical_api_endpoints.py` (whole file), and the
     `TestSessionFlow` class in `test_gesture_liveness_session.py` (needs
     Redis). Requires DeepFace+TF weights, `DATABASE_URL`, Redis.
   - `RUN_FULL_STACK_INTEGRATION=true` → the four `with TestClient(app)`
     **ML-lifespan** files (`test_enroll_liveness_antispoof.py`,
     `test_verify_challenge_endpoint.py`, `test_verify_antispoof_wiring.py`,
     `test_verify_antispoof_block_enforce.py`). The app startup lifespan
     pre-loads torch + the uniface MiniFASNet ONNX; on the lightweight CI
     runner the drifted `>=` deps **segfault** during that load (the same
     native-drift crash as P0-2b) and take down the whole
     `pytest tests/integration/` process (exit 139). Gated so they skip on CI
     and run inside the Docker ML stack (pinned deps).
   - `RUN_PROCTORING_INTEGRATION=true` → `test_proctoring_api.py` (pre-existing).
   - `test_new_api_routes.py` and the feature-flag / shape-template tests run in
     CI with no flag (infra-free).

   On a bare host / lightweight CI runner these gated tests SKIP rather than
   fail. Run the full set inside the Docker ML stack with the flags set.

   **Why this matters:** the CI integration job had been *skipped* for weeks
   because the unit job perpetually failed (masked by `continue-on-error`), so
   it `needs: test` never ran. Making the unit job honestly green (P2-2)
   unblocked the integration job and exposed this latent runner-side segfault;
   the ML-lifespan gate keeps the integration job honestly green too.

Bare-host baseline (no DB/Redis/TF): `tests/unit/` = 647 passed, 1 skipped,
1 xfailed; `tests/integration/` (no flag) = 57 passed, 104 skipped, 0 errors,
no segfault. With `RUN_FULL_STACK_INTEGRATION=true` inside the Docker ML stack
the gated files run.

## Key Directories

- `app/api/routes/` - API route handlers (27 files including `__init__.py`; 26 route modules)
- `app/domain/` - Domain entities and interfaces
- `app/application/use_cases/` - Business logic use cases
- `app/infrastructure/ml/` - ML model implementations (DeepFace, MediaPipe, YOLO)
- `app/infrastructure/persistence/` - Data repositories
- `app/core/` - Configuration and DI container

## Biometric Modality Support

### Fully implemented:
- **Face**: enroll, verify, search, liveness, quality, demographics, landmarks, comparison
- Routes: `enrollment.py`, `verification.py`, `search.py`, `liveness.py`, `quality.py`, etc.
- **Enroll/verify liveness parity (2026-05-29)**: face `/enroll` now runs the SAME
  server-authoritative passive liveness + spoof-detector anti-spoof / EAR veto
  that `/verify` runs, BEFORE persisting the embedding — a photo/screen spoof
  can no longer be enrolled. Gated by `ENROLL_LIVENESS_ENABLED` (default `True`).
  Reuses `LIVENESS_MODE`/`LIVENESS_BACKEND`/`ANTI_SPOOFING_ENABLED`/
  `LIVENESS_VERDICT_POLICY` (conservative) and the `ANTISPOOF_*` flags incl.
  `ANTISPOOF_BLOCK_ENFORCE`; the anti-spoof helpers are imported from
  `verification.py` so both paths share one implementation + one model singleton.
  Single-image `/enroll` only (single still frame, like `/verify`);
  `/enroll/multi` is unchanged.
- **Voice**: enroll, verify, search, delete — Resemblyzer 256-dim speaker embeddings, centroid-based
- Routes: `voice.py`, repo: `pgvector_voice_repository.py`, embedder: `speaker_embedder.py`
- **Fingerprint**: removed (P1.4) — server-side fingerprint biometric processing was a SHA-256 hash placeholder, never a real biometric. Platform fingerprint authentication is delivered via WebAuthn (FIDO2) in identity-core-api, not through this service.

### Verification Pipeline (Phase 8B/8C, 2026-03-28):
- **Document scan** — YOLO-based document detection and classification
- **MRZ parser** — TD1/TD3 machine-readable zone extraction
- **Tesseract OCR** — TC Kimlik field extraction (name, TC number, DOB, photo)
- **Face-to-document matching** — DeepFace cosine similarity between selfie and document photo
- **Liveness pipeline** — server-authoritative liveness verdict with configurable thresholds
- **Video interview upload** — endpoint for verification pipeline video step
- Routes: `verification_pipeline.py` (sub-paths: /document-scan, /data-extract, /face-match, /liveness-check, /pipeline/test, /video-interview)

### Not implemented:
- **Iris**: No endpoints at all

### Client Embedding Observations (Alembic 0004, log-only per D2, 2026-04-14):
- `client_embedding_observations` table — vector(128), no HNSW (log, not search surface)
- Populated via `BackgroundTasks` in `enrollment.py` / `verification.py` with fire-and-forget `record()`
- NEVER used for auth decisions — offline divergence analysis only (128-dim client-side model, identity opaque to server, vs ArcFace 512-dim)

## Known Issues (March 2026)

### CRITICAL:
1. Only 5 of 20+ endpoint groups are consumed by other services

### Integration points:
- Called by **identity-core-api** (Java/Spring on port 8080) via BiometricProcessorClient (API key auth)
- NOT publicly accessible — all external face operations must go through identity-core-api proxy endpoints

Integration audit items are tracked in GitHub issues.
