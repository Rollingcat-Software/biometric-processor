# Changelog - Biometric Processor

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
