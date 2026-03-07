# Biometric Processor - Integration Audit & TODO

> Cross-module integration audit completed March 2026.
> Compares biometric-processor against identity-core-api (consumer) and web-app (indirect consumer).

---

## Module Overview

The biometric-processor is a Python/FastAPI service handling face biometric operations.
It is consumed by:
1. **identity-core-api** via `BiometricServiceAdapter` (server-to-server)
2. **web-app** via `BiometricService.ts` (direct browser-to-API calls)

### Registered Routes (17 modules under `/api/v1`):
- `health` - Health checks
- `enrollment` - Face enrollment (`POST /enroll`)
- `verification` - Face verification (`POST /verify`)
- `liveness` - Liveness/anti-spoofing detection
- `search` - 1:N face search
- `batch` - Batch operations
- `quality` - Face quality assessment
- `multi_face` - Multi-face detection
- `demographics` - Demographic analysis
- `landmarks` - Facial landmarks
- `comparison` - Face comparison
- `similarity_matrix` - Similarity matrix
- `embeddings_io` - Embedding import/export
- `webhooks` - Webhook management
- `proctor` / `proctor_ws` - Exam proctoring
- `live_analysis` - Live video analysis
- `admin` - Admin operations
- `card_type_router` - ID card type detection

---

## Cross-Module Integration Issues

### CRITICAL - Breaking consumer integration

- [ ] **BC1** **Fingerprint/Voice endpoints don't exist** - identity-core-api's `BiometricServiceAdapter` calls `enrollFingerprint()`, `verifyFingerprint()`, `enrollVoice()`, `verifyVoice()` but biometric-processor only handles FACE biometrics. These calls will fail with 404. **Fix**: Either add fingerprint/voice processing to biometric-processor, OR document that identity-core-api should handle these through different services, OR add stub endpoints that return appropriate responses.
- [ ] **BC2** **Web-app `BiometricService.ts` URL mismatch** - Frontend calls `/enroll`, `/verify`, `/search`, `/liveness` directly but doesn't use the correct field names. Frontend sends `user_id` in form data but needs to verify backend expects this field name (check enrollment route schema).
- [ ] **BC3** **API Key authentication** - Web-app sends `X-API-Key` header. Biometric-processor has `api_key_auth.py` middleware. Ensure the API key validation is consistent and documented.

### HIGH - Missing integration features

- [ ] **BH1** **No enrollment status tracking** - identity-core-api's `EnrollmentController` expects enrollment status tracking but biometric-processor's enrollment endpoint is synchronous (enroll face immediately, return result). There's no async job tracking. If identity-core-api's frontend expects `PENDING -> PROCESSING -> SUCCESS/FAILED` lifecycle, biometric-processor needs to support this.
- [ ] **BH2** **No tenant isolation in face DB** - Frontend and identity-core-api send `tenant_id` in enrollment/verification calls. Verify that biometric-processor properly isolates face embeddings by tenant (not mixing faces across tenants).
- [ ] **BH3** **No quality/liveness scores in enrollment response** - Web-app frontend expects `qualityScore` and `livenessScore` in enrollment data. Verify that biometric-processor's enrollment response includes these or that they need to be computed separately via `/quality` and `/liveness` endpoints.
- [ ] **BH4** **Webhook integration with identity-core-api** - biometric-processor has webhook routes but identity-core-api doesn't register any webhooks. For async enrollment processing, webhooks could notify identity-core-api of completion.
- [ ] **BH5** **Proctoring integration** - biometric-processor has exam proctoring endpoints (`/proctor`, WebSocket) but neither identity-core-api nor web-app use them. These are backend capabilities not exposed to end users.

### MEDIUM - API consistency

- [ ] **BM1** **Health endpoint format** - Web-app calls `GET /health` for health check. Verify response format matches what frontend expects (simple boolean check).
- [ ] **BM2** **Response field naming** - biometric-processor uses Python snake_case (`is_real`, `spoof_type`, `user_id`) but frontend expects camelCase in some places. The frontend `BiometricService.ts` manually maps `is_real` -> `isReal` but may miss other fields.
- [ ] **BM3** **Error response format** - Verify biometric-processor error responses are consistent and include proper HTTP status codes that frontend can handle.
- [ ] **BM4** **CORS configuration** - biometric-processor has CORS middleware. Ensure it allows web-app origin for direct browser calls.
- [ ] **BM5** **Rate limiting** - biometric-processor has `RateLimitMiddleware`. Ensure rate limits don't block legitimate enrollment flows from identity-core-api.

### LOW - Documentation and cleanup

- [ ] **BL1** **API documentation** - Generate and maintain OpenAPI spec for consumers. Both identity-core-api and web-app need stable API contracts.
- [ ] **BL2** **Remove demo/test files** - Multiple test/demo files in root (`demo_local.py`, `test_*.py/sh`, `find_good_images.py`, etc.) should be moved to proper test directory or cleaned up.
- [ ] **BL3** **Docker configuration** - Multiple Dockerfiles exist (`Dockerfile`, `Dockerfile.init`, `Dockerfile.laptop-gpu`). Document which to use for production.
- [ ] **BL4** **face_db.pkl in root** - Face database pickle file should not be in repository root. Move to data directory or `.gitignore`.
- [ ] **BL5** **Endpoint documentation for consumers** - Create clear documentation mapping biometric-processor endpoints to identity-core-api's `BiometricServiceAdapter` methods.

---

## Feature Usage Matrix

| Biometric Processor Feature | Used by identity-core-api | Used by web-app | Status |
|-----------------------------|---------------------------|-----------------|--------|
| `POST /enroll` (face) | Yes (BiometricServiceAdapter) | Yes (BiometricService.ts) | Working |
| `POST /verify` (face) | Yes (BiometricServiceAdapter) | Yes (BiometricService.ts) | Working |
| `POST /search` (1:N) | No | Yes (BiometricService.ts) | Working |
| `POST /liveness` | No (done in FaceAuthHandler) | Yes (BiometricService.ts) | Working |
| `GET /health` | No | Yes (BiometricService.ts) | Working |
| `POST /quality` | No | No | Unused |
| `POST /multi-face` | No | No | Unused |
| `POST /demographics` | No | No | Unused |
| `POST /landmarks` | No | No | Unused |
| `POST /compare` | No | No | Unused |
| `POST /similarity-matrix` | No | No | Unused |
| `POST /embeddings/export` | No | No | Unused |
| `POST /embeddings/import` | No | No | Unused |
| `POST /batch/*` | No | No | Unused |
| `/proctor/*` | No | No | Unused |
| `/proctor/ws` | No | No | Unused |
| `/live-analysis` | No | No | Unused |
| `/admin/*` | No | No | Unused |
| `/webhooks/*` | No | No | Unused |
| `/card-type/*` | No | No | Unused |

**Key Finding**: Only 5 of 20+ endpoint groups are actually consumed. The remaining features (quality analysis, demographics, landmarks, proctoring, batch operations, etc.) are available but not integrated into either the identity-core-api or web-app.

---

## Summary

| Priority | Count | Description |
|----------|-------|-------------|
| Critical | 3 | Missing fingerprint/voice endpoints, URL/field mismatches |
| High | 5 | Enrollment lifecycle, tenant isolation, quality scores |
| Medium | 5 | API consistency, CORS, rate limiting |
| Low | 5 | Documentation, cleanup |
| **Total** | **18** | |

### Priority Order

**Week 1**: BC1 (fingerprint/voice strategy), BC2-BC3 (API contract validation)
**Week 2**: BH1-BH3 (enrollment lifecycle, tenant isolation, quality scores)
**Week 3**: BM1-BM5 (API consistency), BH4-BH5 (webhooks, proctoring integration)
**Week 4**: BL1-BL5 (documentation, cleanup)

## AUTH METHOD INTEGRATION GAPS (March 2026)

### Biometric Modality Status

| Modality | Enroll Endpoint | Verify Endpoint | Implementation | Runtime Status |
|---|---|---|---|---|
| FACE | POST /api/v1/enroll | POST /api/v1/verify | Full (DeepFace) | Working |
| FINGERPRINT | POST /api/v1/fingerprint/enroll | POST /api/v1/fingerprint/verify | **Stub only** | **Always fails** |
| VOICE | POST /api/v1/voice/enroll | POST /api/v1/voice/verify | **Stub only** | **Always fails** |
| IRIS | None | None | **Not implemented** | N/A |

### Biometric Integration TODOs

- [ ] **BIO-1** Fingerprint enroll/verify stubs always return `success: false` - identity-core-api FingerprintAuthHandler calls these and always fails
- [ ] **BIO-2** Voice enroll/verify stubs always return `success: false` - identity-core-api VoiceAuthHandler calls these and always fails
- [ ] **BIO-3** No iris biometric support at all (no endpoints, no handler)
- [ ] **BIO-4** Fingerprint stub uses simple JSON body but identity-core-api may send different format via BiometricServiceAdapter
- [ ] **BIO-5** Voice stub uses simple JSON body but identity-core-api may send different format via BiometricServiceAdapter
- [ ] **BIO-6** Decision needed: implement real fingerprint/voice processing OR delegate to platform authenticators (WebAuthn) instead

### Implementation Notes

For fingerprint: Consider using WebAuthn/FIDO2 platform authenticators instead of server-side fingerprint processing. Modern browsers support `navigator.credentials` with Touch ID / Windows Hello. This would bypass the biometric-processor entirely.

For voice: Requires ML model for speaker verification (e.g., Resemblyzer, SpeechBrain). Significant effort. Currently lowest priority.

---

### Strategic Decision Needed

The biometric-processor has many advanced features (proctoring, demographics, landmarks, batch processing) that are not used by either consumer. Decision needed:
1. **Integrate these into web-app** as premium features (significant frontend work)
2. **Keep them as API-only** for direct API consumers
3. **Remove unused endpoints** to reduce maintenance burden
