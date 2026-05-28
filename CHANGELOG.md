# Changelog - Biometric Processor

## [Unreleased]

### Docs — 2026-05-28 (freshness audit)
- Corrected stale config defaults (`VERIFICATION_THRESHOLD` 0.6 → 0.45, `LIVENESS_MODE` code default vs prod override documented)
- Added missing env vars (`FIVUCSAS_EMBEDDING_KEY`, `ANTISPOOF_BLOCK_ENFORCE`) to README and DOCKER_SETUP
- Marked GPU-only models/backends (`ArcFace`, `VGG-Face`, `GhostFaceNet`, `retinaface`, `yolo*`) with `ALLOW_HEAVY_ML=true` requirement
- Fixed Quick Start demo script name (`demo_local.py` → `demo_local_fast.py`)
- Fixed API auth header (`Authorization: Bearer` → `X-API-Key`) in API_DOCUMENTATION
- Corrected Python version references from 3.11 to 3.12
- Fixed route module count in CLAUDE.md (17 → 27 files / 26 route modules)
- Removed MobileFaceNet attribution from client-embedding description in CLAUDE.md
- Corrected CLAUDE.md route references: removed non-existent `document.py` / `video_interview.py`, removed `TODO.md` reference
- Closed voice roadmap items (fully shipped: /voice/enroll|verify|search|delete, Resemblyzer 256-dim)
- Added anti-spoof algorithm provenance note to ARCHITECTURE.md
- Migrated DOCKER_SETUP.md to `docker compose` v2 syntax; added prod usage section
- Documented undocumented endpoints in README (flash-challenge, nfc, proctoring, liveness-puzzle, verification sub-paths, admin, health probes, metrics)
- Updated copyright year 2025 → 2026

## [2026-05-12] ML review — anti-spoof enforcement + EAR + verify hardening

### Security / Fixes (PR #102)
- **Anti-spoof block enforcement**: `ANTISPOOF_BLOCK_ENFORCE` (default `true`) — assembler "block" verdicts and EAR closed-eye signals now return HTTP 403 (was advisory-only).
- **EAR veto** (`ANTISPOOF_EAR_VETO_ENABLED`, default `false`): single-frame Eye Aspect Ratio closed-eye detection on `/verify`; fails-soft when `face_landmarker.task` asset is absent.
- **Aged-threshold inversion fix**: `VERIFICATION_THRESHOLD_AGED` default corrected from 0.38 to 0.55 (under `distance < threshold`, a lower aged threshold made aged users stricter — the opposite of intent).
- **SHA-256 model pin**: model file integrity checked at startup.
- **Verify-challenge endpoint** added to liveness puzzle router.

## [2026-05-11] Paper P0 + blink cache + anti-spoof wiring

### Features / Fixes
- EAR/blink cache wired from `spoof-detector` package (paper P0, PR #89/#88).
- Anti-spoof flags (`ANTISPOOF_*`) wired through to the assembler (PR #89).
- `spoof-detector` bumped to v0.2.1; `git` added to Dockerfile so pip can fetch the git dep (PR #90).
- NFC MRZ route exposed at `/api/v1/nfc/mrz` (PR #95).
- Real occlusion detection + liveness contradiction policy (PR #94).
- CI green-up: stale test repair across 7 commits (PR #99 + follow-ups).

## [2026-05-07] Embedding encryption-at-rest + P0 session

### Security
- Embedding Fernet encryption-at-rest activated: `pgvector_embedding_repository` now reads/writes ciphertext column with `EmbeddingCipher.from_env()` (PR #73). `FIVUCSAS_EMBEDDING_KEY` is a hard boot requirement from this point.
- `FIVUCSAS_EMBEDDING_KEY` wired through to runtime container in `docker-compose.prod.yml` (PR #78).
- Live-camera analysis fail-closed when liveness detector unavailable (PR #74).
- Anti-replay counts corrupt frames as failures (PR #76).
- Liveness verdict policy + 413 i18n (PR #77).

### Docs — 2026-04-26 (iOS / macOS scope dropped — no-op for this repo)
- Parent FIVUCSAS scope updated 2026-04-26 to permanently drop iOS / iPadOS / macOS (no Apple hardware available). This repo's `README.md`, `ROADMAP.md`, and `CHANGELOG.md` had no forward-looking iOS/macOS content; macOS-as-developer-environment install instructions for Redis and PostgreSQL in `README.md` are unaffected. No code or config changes required.

## [2026-04-19] Audit remediation

Remediation for findings from `docs/audits/AUDIT_2026-04-19.md` (Audit 2 — ML
security). No container rebuild, no commits in this changeset.

### Security
- **ML-C1** (already landed earlier this session) — face + voice pgvector
  `find_similar`/`delete` now require a non-null `tenant_id`; `/search` route
  rejects cross-tenant queries at the SQL layer.
- **ML-H2** — `PIL.Image.MAX_IMAGE_PIXELS = 50_000_000` set at app init to
  block decompression-bomb uploads.
- **ML-H3** — API-key comparison uses `hmac.compare_digest` in `app/main.py`
  and `simple_api_key_middleware.py` (constant-time comparison).
- **ML-H4** — Voice replay-detection skeleton added
  (`app/infrastructure/ml/voice/replay_detector.py`). Spectral-fingerprint
  cosine-similarity check against a per-user Redis LRU cache; structured
  `voice_replay_suspect` log + Prometheus counter. Log-only, gated by
  `VOICE_REPLAY_DETECTION_ENABLED=false` by default.
- **ML-M1** — DeepFace model integrity verification after
  `DeepFace.build_model(...)` — SHA256 of the Facenet512 weight file is
  compared against `settings.DEEPFACE_FACENET512_SHA256`. Empty pinned hash
  logs a warning but does not raise (deploy safety). Mismatch raises
  `RuntimeError("DeepFace model integrity check failed")` to halt startup.
- **ML-M3** — Liveness-step temp-JPEG cleanup in `verification_pipeline.py`
  now uses `try/finally` around `liveness_uc.execute()` so the file cannot
  leak on exception.
- **ML-M4** — Batch endpoints (`/batch/enroll`, `/batch/verify`) are gated
  by a module-level `asyncio.Semaphore(settings.BATCH_MAX_CONCURRENT)` to
  bound in-flight concurrency (default 4).
- **ML-M5** — `find_similar` on face and voice repositories clamps caller-
  supplied `threshold` and `limit` against server-side caps
  (`FIND_SIMILAR_FACE_MAX_THRESHOLD=0.8`,
  `FIND_SIMILAR_VOICE_MAX_THRESHOLD=0.7`, `FIND_SIMILAR_MAX_LIMIT=50`) and
  logs a warning when clamping occurs.

### Config
- New settings in `app/core/config.py`:
  `DEEPFACE_FACENET512_SHA256`, `FIND_SIMILAR_FACE_MAX_THRESHOLD`,
  `FIND_SIMILAR_VOICE_MAX_THRESHOLD`, `FIND_SIMILAR_MAX_LIMIT`,
  `VOICE_REPLAY_DETECTION_ENABLED`, `VOICE_REPLAY_CACHE_SIZE`,
  `VOICE_REPLAY_SIMILARITY_THRESHOLD`.
- `BATCH_MAX_CONCURRENT` default lowered from 5 to 4 to match the
  semaphore guard and the audit recommendation.

### Tests
- `tests/unit/infrastructure/test_voice_replay_detector.py` —
  same-fingerprint-twice flagged; feature-flag-off is a no-op; different
  audio not flagged.

### P1.2 / ML-H1 follow-up
- `requirements-lock.txt` left annotated with a `REGENERATE-ME` preamble.
  Full regeneration punted — see report and GitHub issue #47.

## [Unreleased] - 2026-03-07

### Added
- CLAUDE.md with project context, known issues, and biometric modality status
- ROADMAP.md with phased biometric expansion plan
- Biometric modality integration gap analysis in TODO.md (6 new items: BIO-1 through BIO-6)

### Documented
- Biometric modality status matrix: Face fully working, Fingerprint/Voice are stubs, Iris not implemented
- Fingerprint/Voice stubs cause identity-core-api auth handlers to always fail at runtime
- Only 5 of 20+ endpoint groups are consumed by other services
- Strategic decision needed on unused feature endpoints

### Previous
- Cross-module integration audit (March 2026): 18 issues identified
- Face biometrics fully operational (enroll, verify, search, liveness, quality)
