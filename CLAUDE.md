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
   - `RUN_FULL_STACK_INTEGRATION=true` → a few **cross-file loop-poisoned** /
     flaky tests: a function-scoped/inline `TestClient(app)` (no `with`
     lifespan) hits `RuntimeError: Event loop is closed` once an earlier
     lifespan-managed client in the same process shut down the shared anyio
     portal — `test_gesture_liveness_session.py` `TestFeatureFlag` +
     `TestShapeTemplatesEndpoint`, `test_new_api_routes.py`
     `TestSimilarityMatrixEndpoint` — plus one flaky wall-clock perf assertion
     (`test_performance_with_real_images.py::test_hash_performance`, avg<5ms).
     They pass in isolation / in the Docker ML stack.
   - Everything else infra-free runs in CI with no flag.

   On a bare host / lightweight CI runner these gated tests SKIP rather than
   fail. Run the full set inside the Docker ML stack with the flags set.

   **Why this matters:** the CI integration job had been *skipped* for weeks
   because the unit job perpetually failed (masked by `continue-on-error`), so
   it `needs: test` never ran. Making the unit job honestly green (P2-2)
   unblocked the integration job and exposed (a) a latent runner-side ML-load
   segfault and (b) these cross-file isolation/flake bugs; the env gates keep
   the integration job honestly green too.

**Current state (2026-05-30, main `fbe70b7`): all five CI jobs GREEN** — Lint,
Security, Unit Tests, Integration Tests, Build Frontend — with NO
`continue-on-error` and NO `--ignore` flags.

Bare-host baseline (no DB/Redis/TF): `tests/unit/` = 647 passed, 1 skipped,
1 xfailed; `tests/integration/` (no flag) = 50 passed, 111 skipped, 0 errors,
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
- **Multi-image enroll liveness (2026-05-30)**: `/enroll/multi` now also runs the
  SAME passive-liveness `CheckLivenessUseCase` that single-`/enroll` calls — on
  EVERY submitted frame, BEFORE its embedding is extracted/fused, **fail-CLOSED**
  (one non-live frame rejects the whole enrollment with `LivenessCheckFailedError`
  → HTTP 400). Closes the documented gap where a photo could be enrolled via the
  multi-image path. Wired in `enroll_multi_image.py` (the use case takes an
  optional `liveness_use_case`; `get_enroll_multi_image_use_case()` injects it).
  Same `ENROLL_LIVENESS_ENABLED` flag (default `True`); when the use case is
  built without a checker (legacy/unit-test callers) the gate is skipped.
  CPU-only.
- **Multi-image enroll quality-floor + per-frame skip (fix #7, 2026-06-03)**:
  two related hardenings in `enroll_multi_image.py` / `config.py`. (1) The
  per-frame quality floor `MULTI_IMAGE_MIN_QUALITY_PER_IMAGE` default dropped
  **60.0 → 40.0** to match the single-image `QUALITY_THRESHOLD` (=40 in prod),
  removing the asymmetry where a 40-59-scoring frame passed single `/enroll`
  but was rejected per-frame on `/enroll/multi` (env-overridable). (2) A frame
  that fails ONLY the per-frame **quality** gate (`PoorImageQualityError`, or
  defensively `FaceNotDetectedError`) is now **skipped** — logged, not fused —
  and the loop continues toward `MULTI_IMAGE_MIN_IMAGES`; one weak photo no
  longer aborts the whole batch. If too many frames are skipped to reach the
  minimum, `InsufficientImagesError` is raised (HTTP-mapped) so the user is
  told to retry. **Security preserved**: liveness (`LivenessCheckFailedError`)
  and anti-spoof (`SpoofDetectedError`) failures, ML timeouts, MultipleFaces,
  and any unexpected error stay **FATAL** (abort fail-closed) — only
  quality-class failures are skippable (see `_SKIPPABLE_FRAME_ERRORS`).
- **Voice**: enroll, verify, search, delete, **exists** — Resemblyzer 256-dim speaker embeddings, centroid-based
- Routes: `voice.py`, repo: `pgvector_voice_repository.py`, embedder: `speaker_embedder.py`
- **Enrollment-existence probes (login triage F2/F7/F9, 2026-06-12):**
  `GET /voice/{user_id}/exists` and `GET /face/{user_id}/exists` return
  `{user_id, exists}` via a cheap `SELECT EXISTS(...)` against
  `voice_enrollments` / `face_embeddings` (`repo.exists`) — NO inference, NO
  vector decrypt. Face accepts an optional `?tenant_id=` (verify-path parity);
  voice is user-scoped only (matches `/voice/verify`). identity-core-api's
  `EnrollmentHealthService` calls these so FACE/VOICE are only reported enrolled
  for users who genuinely have a template, instead of the prior "trust if the
  service is reachable" fake that routed un-enrolled users into a voice step that
  could never pass. Same `X-API-Key` auth as every other `/api/*` route.
- **Voice verify centroid normalization (P1-10, 2026-06-02)**: the default enroll
  path stores the centroid as `AVG(embedding)::vector` (the mean of unit-norm
  embeddings has norm < 1 and shrinks as enrollments accumulate). `/voice/verify`
  now L2-normalizes BOTH the probe and the stored centroid before the dot product
  so `confidence` is a true cosine similarity, invariant to enrollment count
  (previously decayed ≈0.71 @2 → ≈0.47 @5 and false-rejected genuine users). The
  accept threshold is UNCHANGED (verify ≥ 0.65). The `optimize=True` re-enroll
  fusion path already L2-normalizes its centroid, and `/voice/search` uses
  pgvector `<=>` cosine distance (norm-invariant) — both unaffected.
- **Fingerprint**: removed (P1.4) — server-side fingerprint biometric processing was a SHA-256 hash placeholder, never a real biometric. Platform fingerprint authentication is delivered via WebAuthn (FIDO2) in identity-core-api, not through this service.

### Client-computed face embedding (flag-gated, default OFF — 2026-06-12):
The browser can compute the authoritative Facenet512 embedding locally
(onnxruntime-web) and submit ONLY the 512-d vector — the raw face image never
leaves the device. Two additive JSON routes accept it:
- **`POST /verify-embedding`** (`verification.py`) — `{tenant_id, user_id,
  embedding[512]}`. Runs the SAME `match_embedding` / pgvector cosine + threshold
  + aged-adaptation as the image `/verify`, but SKIPS detect, quality, liveness and
  the server-side Facenet512 forward pass (the client already produced the vector).
  The schema validates the length to exactly 512 (HTTP 422 otherwise). Anti-spoof
  response fields are always `None` (no image).
- **`POST /enroll-embedding`** (`enrollment.py`) — stores the client vector as the
  template (encrypt-at-rest + dual-column persist), skipping the server embed.
- **SECURITY — NO LIVENESS HERE.** These paths receive no image, so no liveness /
  anti-spoof check is (or can be) performed. They therefore REQUIRE a paired
  liveness factor (passive or the puzzle layer) enforced at the Identity Core layer
  before the result is trusted as a login factor. On its own a matched embedding
  only proves "this vector matches the template", not "a live person produced it now".
- Gated by Identity Core `app.auth.client-side-embedding`. The CODE default is OFF, but
  **production `.env.prod` sets `APP_AUTH_CLIENT_SIDE_EMBEDDING=true` (global, tenants list
  empty) → client-side embedding IS the PRODUCTION DEFAULT for face enroll AND verify**
  (verified live 2026-06-14: `FaceEnrollmentDialog.tsx:59` + `BiometricService.ts:220`
  `/enroll-embedding`; verify → `/verify-embedding`). Don't be misled by the code default —
  prod runs client-side. The legacy image `/verify` + `/enroll` path remains in code as the
  disabled fallback. (The thesis was corrected to match this: FIVUCSAS #213/#214.)
- Privacy framing: the raw image is not transmitted; the only biometric data sent is
  a derived, non-invertible 512-d embedding, over TLS, stored encrypted (Fernet) —
  data minimization, NOT "biometric data never leaves the device".

### Client-computed VOICE embedding (GPU-less, audit H3, flag-gated, default OFF — 2026-06-12):
Mirror of the face embedding path for VOICE. The browser computes the 256-d
Resemblyzer GE2E speaker embedding locally (onnxruntime-web) and submits ONLY the
vector — the raw audio never leaves the device; the server skips decode/VAD/forward.
Two additive JSON routes in `voice.py`:
- **`POST /voice/verify-embedding`** — `{user_id, embedding[256]}`. Runs the SAME
  pgvector cosine compare + 0.65 threshold as the audio `/voice/verify` (both share
  the `_match_probe_against_enrollment` helper + module-level `VERIFY_THRESHOLD`),
  but SKIPS the audio decode, VAD, quality scoring, replay check and the server-side
  Resemblyzer forward pass. Length-validated to exactly 256 (HTTP 422 otherwise).
- **`POST /voice/enroll-embedding`** — `{user_id, embedding[256], optimize?}`. Stores
  the client vector via the SAME `PgVectorVoiceRepository.save` centroid path (INDIVIDUAL
  row + recomputed CENTROID, encrypt-at-rest) as audio `/voice/enroll`; no decoded audio
  to score, so `quality_score` is a neutral 0.5. `optimize=True` takes the re-enroll fusion path.
- **SECURITY — NO REPLAY/LIVENESS HERE.** No audio ⇒ the spectral-fingerprint replay
  detector (needs decoded samples) can't run, and there's no live-capture proof. REQUIRES
  a paired liveness factor enforced at the Identity Core layer. Gated by Identity Core
  `app.auth.client-side-voice-embedding` (default OFF); the audio `/voice/verify` +
  `/voice/enroll` path is unchanged and remains the default + fallback.
- **ONNX export (DONE + VERIFIED):** `scripts/export_resemblyzer_onnx.py` exports the
  pinned `resemblyzer/pretrained.pt` (1.42M-param 3-layer LSTM + Linear) to ONNX
  (opset 17, FP32, ~5.7 MB, dynamic n_frames). torch↔ONNX cosine parity = 1.0 (random mel
  batches + end-to-end vs `embed_utterance`). The export FAILS if parity < 0.999.
- **Client preprocessing port = SCAFFOLD (NOT verified).** The browser must reproduce
  resemblyzer's `preprocess_wav` (dBFS norm + WebRTC VAD mode-3 silence trim) +
  `wav_to_mel_spectrogram` (librosa power-mel, n_fft 400 / hop 160 / 40 mels) +
  partial-slice/mean/L2-norm. The WebRTC VAD has no bit-exact JS port; skipping it
  measured ≈0.89 same-clip cosine vs server (impostor ≈0.40) — risky near the 0.65
  threshold. Full load-bearing contract + canary steps:
  `docs/design/VOICE_CLIENT_EMBEDDING_SPEC.md`. Do not enable the web flag until the
  client mel+VAD is validated to parity.
- NOTE: the `get_speaker_embedder` container comment claiming "numba-free MFCC + torch
  projection" was WRONG and is now corrected — it is the real ~17 MB pretrained
  Resemblyzer GE2E LSTM (librosa supplies the mel input).

### Puzzle liveness session (flag-gated, default OFF — server-authoritative, anti-replay):
`puzzle.py` exposes a server-issued, single-use liveness session that spans the 14
face + 9 hand challenge types (canonical contract:
`docs/superpowers/plans/2026-06-12-puzzle-session-convergence.md`):
- **`POST /liveness/puzzle-session`** — `{tenant_id, user_id, allowed_challenge_types,
  count, difficulty}`. `PuzzleSessionManager` randomly selects `count` challenges,
  stores session state (session_id, issued challenges, status, TTL 300s, single-use,
  owner = user_id + tenant_id), returns `{session_id, challenges}`.
- **`POST /liveness/puzzle-session/{session_id}/challenge`** — scores the uploaded
  landmark/gesture traces against the issued challenge (metric REQUIRED — absent/empty
  fails), marks the challenge complete. Used by the client for per-challenge UX only.
- **`POST /liveness/puzzle-session/{session_id}/verdict`** — `verified` =
  (all issued challenges validated) AND (owner matches) AND (not expired) AND
  (not already consumed); CONSUMES the session (single-use). This is the auth gate.
- Reachable only via the Identity Core MFA-flow proxy (`/auth/mfa/puzzle/session*`,
  X-API-Key); bio is the sole scoring authority — the client never sends a trusted
  "passed" boolean. Random per-attempt challenges + single-use session defeat replay.

### Verification Pipeline (Phase 8B/8C, 2026-03-28):
- **Document scan** — YOLO-based document detection and classification
- **MRZ parser** — TD1/TD3 machine-readable zone extraction
- **Tesseract OCR** — TC Kimlik field extraction (name, TC number, DOB, photo)
- **Face-to-document matching** — DeepFace cosine similarity between selfie and document photo
- **Liveness pipeline** — server-authoritative liveness verdict with configurable thresholds
- **Video interview upload** — endpoint for verification pipeline video step
- Routes: `verification_pipeline.py` (sub-paths: /document-scan, /data-extract, /face-match, /liveness-check, /pipeline/test, /video-interview)

### NFC document (`nfc.py`):
- **`POST /nfc/mrz`** — pure MRZ string parsing (TD1/TD3, DG1 envelope or raw text).
- **`POST /nfc/verify-authenticity` (2026-05-30)** — ICAO 9303 Part 11 **passive
  authentication** (eMRTD chip trust). Accepts `{sod_b64, data_groups:{"<dg#>":b64}}`
  and verifies, fail-CLOSED: (a) each provided DG hash matches the signed value
  in EF.SOD's `LDSSecurityObject`, (b) the SOD's CMS signature verifies under the
  embedded Document Signer cert, (b2, BIO-M2 2026-06-02) the DS cert AND the CSCA
  root it chains to are each within their `[not_valid_before, not_valid_after]`
  validity window (an expired/not-yet-valid DS → `reason_code=DS_CERT_EXPIRED`; an
  expired CSCA anchor → `CSCA_CERT_EXPIRED`), (c) DS chains to a trusted CSCA root. Returns
  `{is_authentic, reason, reason_code, ds_subject, ds_serial, csca_matched,
  dg_hash_results, sod_hash_algorithm}`. Pure Python crypto (`asn1crypto` +
  `cryptography`) — **no GPU, no ML**. Logic lives in the framework-free domain
  service `app/domain/services/emrtd_passive_auth.py`. Consumed by
  identity-core-api `NfcDocumentAuthHandler` via `BiometricServicePort`.
  - **CSCA trust store** is an OPERATOR deliverable: drop CSCA root certs
    (PEM/DER) into `NFC_CSCA_TRUST_DIR` (default `app/core/csca_trust_store/`, see
    its README). Empty store ⇒ `is_authentic=false` / `reason_code=NO_TRUST_STORE`.
    Loaded at request time (mtime-keyed cache), so adding a cert needs no rebuild.

### Not implemented:
- **Iris**: No endpoints at all

### Client Embedding Observations (Alembic 0004, log-only per D2, 2026-04-14):
- `client_embedding_observations` table — vector(128), no HNSW (log, not search surface)
- Populated via `BackgroundTasks` in `enrollment.py` / `verification.py` with fire-and-forget `record()`
- NEVER used for auth decisions — offline divergence analysis only (the legacy 128-dim landmark-geometry client signal, identity opaque to server, vs the 512-dim Facenet512 template)
- NOTE: this is the OLD log-only client signal. It is distinct from the new
  authoritative **client-computed Facenet512 512-d vector** (`/verify-embedding`,
  `/enroll-embedding`, flag-gated) documented in the Face section above — that vector
  IS the template / match input when the flag is ON; this 128-d observation never is.

## Known Issues (March 2026)

### CRITICAL:
1. Only 5 of 20+ endpoint groups are consumed by other services

### Integration points:
- Called by **identity-core-api** (Java/Spring on port 8080) via BiometricProcessorClient (API key auth)
- NOT publicly accessible — all external face operations must go through identity-core-api proxy endpoints

Integration audit items are tracked in GitHub issues.
