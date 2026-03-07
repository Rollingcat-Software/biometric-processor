# Biometric Processor - Roadmap

## Biometric Modality Roadmap

### Phase 1: Fix Integration Gaps (Priority: Critical)

- [ ] Improve fingerprint stub to return structured error responses matching BiometricServiceAdapter expectations
- [ ] Improve voice stub to return structured error responses matching BiometricServiceAdapter expectations
- [ ] Document which biometric modalities are implemented vs stubbed for consumers
- [ ] Verify face enrollment/verification field names match BiometricServiceAdapter

### Phase 2: Expand Biometric Support (Priority: High)

- [ ] Evaluate fingerprint processing options:
  - Option A: WebAuthn/FIDO2 platform authenticators (recommended for web)
  - Option B: Server-side fingerprint template matching (requires SDK)
- [ ] Evaluate voice processing options:
  - Option A: SpeechBrain speaker verification model
  - Option B: Resemblyzer voice embeddings
- [ ] Add tenant isolation for face embeddings database
- [ ] Add enrollment status tracking (async lifecycle: PENDING -> PROCESSING -> SUCCESS/FAILED)

### Phase 3: Production Hardening (Priority: Medium)

- [ ] Connect webhook system to identity-core-api for async enrollment notifications
- [ ] Integrate proctoring endpoints with web-app
- [ ] Add quality/liveness scores to enrollment response for frontend consumption
- [ ] Export stable OpenAPI spec for consumers

### Phase 4: Cleanup (Priority: Low)

- [ ] Move demo/test files from root to proper directories
- [ ] Document Docker configuration (which Dockerfile for production)
- [ ] Move face_db.pkl to data directory
- [ ] Evaluate and remove unused endpoints (15+ unused features)
