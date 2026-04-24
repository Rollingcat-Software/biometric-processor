# MediaPipe Hand Landmarker — License Record

- **Date recorded:** 2026-04-24
- **Model file:** `hand_landmarker.task` (7.5 MB)
- **License:** Apache License 2.0 (per MediaPipe GitHub repository and the
  official model card)
- **Source:** https://developers.google.com/mediapipe/solutions/vision/hand_landmarker
- **Publisher:** Google LLC

## Redistribution note

Apache License 2.0 permits redistribution — including in commercial SaaS
products — provided attribution is preserved.

For this project, attribution lives in the repository-root `NOTICE` file:

> This product includes models published by Google LLC under Apache License
> 2.0 — MediaPipe Hand Landmarker.

If `hand_landmarker.task` is shipped to clients (e.g. as a downloadable,
SHA256-verified static asset), the `NOTICE` file MUST remain reachable to
end users (served with the SDK / linked from the licensing page).

## Usage in this project

MediaPipe is **client-side only**. The biometric-processor server never
runs MediaPipe inference; it only:

1. Stores `hand_landmarker.task` as a static asset to be served to clients.
2. Verifies an expected SHA256 hash (see
   `GESTURE_HAND_LANDMARKER_MODEL_SHA256` in `app/core/config.py`) so the
   asset can be rotated centrally without re-releasing client applications.
3. Accepts 21-point landmark arrays shipped from the client and runs
   deterministic geometry checks (no ML inference).

As a result this project does **not** import `mediapipe` for gesture
liveness on the server side — only the client-side apps do.

## Verify current license

If the model file is ever re-downloaded or updated, a future maintainer
MUST re-check the license by:

1. Visiting the official model card URL above.
2. Confirming the "License" section still reads "Apache License 2.0".
3. Downloading the latest `hand_landmarker.task`, computing its SHA256 with
   `sha256sum hand_landmarker.task`, and updating both this document and
   the `GESTURE_HAND_LANDMARKER_MODEL_SHA256` env value shipped to production.
4. Checking upstream MediaPipe release notes
   (https://github.com/google-ai-edge/mediapipe/releases) for any license
   changes between the previous and new versions.

If the upstream license ever changes to something more restrictive (e.g.
non-commercial), the asset must be removed from distribution immediately
and this file updated to reflect that.
