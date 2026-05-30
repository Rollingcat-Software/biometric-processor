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

## ✅ Canonical reproducible build RESTORED — P0-2b (2026-05-30)

**The from-scratch `Dockerfile` build now BOOTS CLEAN under the prod
`read_only`+`cap_drop` runtime — verified, ready to deploy + retire the overlay.**

### What was wrong (history)
The deployed prod image (`75347c98…`, healthy) was built ~2 weeks before this and
`requirements.txt` historically pinned everything with `>=`, so a fresh rebuild
drifted ~42 packages (numpy 2.4.4→2.4.6, protobuf 7.34.1→7.35.0, uniface
3.6.0→3.7.0, fastapi, nvidia-*, …) AND the floating `python:3.12-slim` base moved
Debian 13.4→13.5. The drifted set **segfaulted** during the UniFace MiniFASNet ONNX
session preload at full-app boot under `read_only`+`cap_drop:ALL` (a native-ABI
interaction — an isolated MiniFASNet load works fine; it was the combination).

### The fix (P0-2b)
1. **Both `FROM` lines in `Dockerfile` are now pinned by DIGEST**
   (`python:3.12-slim@sha256:090ba77e…`) so the base can never float again. (The
   13.4-era trixie digest is no longer tag-served — Docker Hub overwrote the
   `3.12.13-slim` tag with the 13.5 rebuild on 2026-05-22 — so this pins the
   *settled* 13.5 digest. The boot test below proves settled-13.5 + the pinned
   native set is fine; the segfault was the floating *drift*, not 13.5 per se.)
2. **Deps install from `requirements-known-good-2026-05-29.lock` applied as a pip
   `-c` constraints file** over the staged ML install + `requirements.txt`, so every
   transitive (torch 2.11.0+cu130, onnxruntime 1.26.0, numpy 2.4.4, uniface 3.6.0,
   nvidia-cu13, …) resolves to the exact proven version. The tf-cpu/deepface/opencv
   special-casing is preserved: the lock's `tensorflow==`, `deepface==`,
   `opencv-python-headless==` and the `spoof-detector @ git+` lines are stripped from
   the constraints (we install `tensorflow-cpu`, deepface `--no-deps`, and headless
   opencv separately) so the lock's plain-`tensorflow` line can't force a GPU-only
   resolution. One lock edit: `idna 3.14→3.15` (pure-Python, the only lock↔
   requirements.txt conflict, needed to satisfy the `idna>=3.15` security floor).

### Boot-test result (2026-05-30, isolated, prod runtime)
Built to a throwaway tag and booted under an isolated copy of
`docker-compose.prod.yml`'s hardening (`read_only`+`tmpfs`+`cap_drop:ALL`+
`cap_add CHOWN/SETUID/SETGID`+`no-new-privileges`), on the `backend` network with
shared-postgres/redis, the prod `biometric-api` container untouched. With the uniface
ONNX seeded into the cache volume (as in real prod), boot logged:
`Pre-loading UniFace MiniFASNet (process-wide shared ONNX session)…` →
**`UniFace MiniFASNet model loaded (process-wide shared session)`** →
`Startup health-check: liveness detector OK` → `Application startup complete` →
`/api/v1/health` **HTTP 200**. **Zero segfault/SIGSEGV signatures, 0 restarts, no
OOM.** The exact previously-segfaulting ONNX session load now succeeds.

### Deploy (operator) — retire the overlay
```bash
cd /opt/projects/fivucsas/biometric-processor
docker compose -f docker-compose.prod.yml --env-file .env.prod build biometric-api   # canonical Dockerfile, digest-pinned
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d biometric-api
# rollback: retag biometric-processor-biometric-api:working-75347c98 → :latest, up -d
```
Two earlier rebuild blockers remain fixed in `docker-compose.prod.yml` (cap_add
CHOWN/SETUID/SETGID for the gosu drop; DeepFace SHA pin forwarded from .env.prod).

### Overlay (still available as fallback)
`Dockerfile.liveness-overlay` (code-only layer `FROM` the proven `75347c98` image)
remains in-repo as the zero-risk fallback path if a future base/lock refresh
reintroduces drift. It is NO LONGER the required deploy path.

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
   - `RUN_PROCTORING_INTEGRATION=true` → `test_proctoring_api.py` (pre-existing).
   - `test_new_api_routes.py` and the feature-flag / shape-template tests run in
     CI with no flag (infra-free).

   On a bare host / lightweight CI runner these gated tests SKIP rather than
   fail. Run the full set inside the Docker ML stack with the flags set.

Bare-host baseline (no DB/Redis/TF): `tests/unit/` = 647 passed, 1 skipped,
1 xfailed; the five formerly-ignored integration files = 7 passed, 77 skipped,
0 errors. (`tests/integration/test_verify_challenge_endpoint.py` needs
`DATABASE_URL`; CI provides Postgres so it is green there — it errors only on a
bare host without a DB.)

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
