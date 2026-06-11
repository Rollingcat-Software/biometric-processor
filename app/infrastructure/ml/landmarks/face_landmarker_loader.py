"""Shared MediaPipe Face Landmarker (Tasks API) loader.

Centralises the `.task` model resolution + SHA256 integrity check used by
every server-side consumer of facial landmarks. Replaces the deprecated
`mediapipe.solutions.face_mesh` API (removed in mediapipe 0.10.35).

The loader honours:
- ``FACE_LANDMARKER_MODEL_PATH`` env var (per-env override).
- A repo-relative ``./models/face_landmarker.task`` default.
- ``FACE_LANDMARKER_MODEL_SHA256`` env var for integrity verification
  (warn-and-disable on mismatch; production MUST set this).

Consumers should treat the returned object as opaque and call ``.detect()``
or ``.detect_for_video()`` against an ``mp.Image`` instance.

This module DOES NOT cache the loader globally; each consumer keeps a
process-local cache appropriate to its lifecycle (singleton vs. per-request).
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default location: <repo>/models/face_landmarker.task. The file is gitignored
# but is baked into the runtime container by the Dockerfile (see PR
# `port: migrate from mp.solutions to mp.tasks.vision`).
_DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "models" / "face_landmarker.task"
)


def resolve_face_landmarker_model_path() -> Optional[Path]:
    """Return the on-disk path to face_landmarker.task or None if absent.

    Resolution order:
      1. ``FACE_LANDMARKER_MODEL_PATH`` env var (if set, must exist).
      2. ``<repo>/models/face_landmarker.task``.
      3. ``./models/face_landmarker.task`` relative to cwd (dev fallback).
    """
    env_path = os.getenv("FACE_LANDMARKER_MODEL_PATH", "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(_DEFAULT_MODEL_PATH)
    candidates.append(Path("models/face_landmarker.task"))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def verify_model_sha256(model_path: Path) -> bool:
    """Verify the SHA256 of the model file against ``FACE_LANDMARKER_MODEL_SHA256``.

    Returns True when:
      - The env var is unset (verification skipped — dev only).
      - The env var matches the on-disk file.

    Returns False when the env var is set and the digest mismatches.
    Logs a warning either way.
    """
    expected = os.getenv("FACE_LANDMARKER_MODEL_SHA256", "").strip()
    if not expected:
        logger.warning(
            "FACE_LANDMARKER_MODEL_SHA256 not set — model integrity NOT verified. "
            "Set this in production to prevent supply-chain tampering."
        )
        return True
    try:
        actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
    except OSError as exc:
        logger.error("Could not read face_landmarker.task for SHA256 check: %s", exc)
        return False
    if actual.lower() != expected.lower():
        logger.error(
            "face_landmarker.task SHA256 mismatch: expected=%s actual=%s path=%s",
            expected,
            actual,
            model_path,
        )
        return False
    return True


def create_face_landmarker(
    *,
    static_image_mode: bool = True,
    num_faces: int = 1,
    output_face_blendshapes: bool = False,
    min_face_detection_confidence: float = 0.5,
    min_face_presence_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> Optional[Any]:
    """Create a MediaPipe FaceLandmarker (Tasks API) or return None on failure.

    Args mirror the relevant subset of the legacy ``mp.solutions.face_mesh``
    constructor so call sites can be ported in-place. ``static_image_mode``
    maps to ``RunningMode.IMAGE`` (True) or ``RunningMode.VIDEO`` (False).

    Returns:
        FaceLandmarker instance ready for ``.detect(mp_image)`` (IMAGE mode) or
        ``.detect_for_video(mp_image, timestamp_ms)`` (VIDEO mode). Returns
        ``None`` if MediaPipe is missing, the model file is absent, or the
        SHA256 check fails — callers should fail-soft.
    """
    try:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError as exc:
        logger.error("MediaPipe Tasks API not importable: %s", exc)
        return None

    model_path = resolve_face_landmarker_model_path()
    if model_path is None:
        logger.warning(
            "face_landmarker.task not found. Set FACE_LANDMARKER_MODEL_PATH or "
            "place the asset under <repo>/models/."
        )
        return None
    if not verify_model_sha256(model_path):
        return None

    try:
        running_mode = mp_vision.RunningMode.IMAGE if static_image_mode else mp_vision.RunningMode.VIDEO
        base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=running_mode,
            num_faces=num_faces,
            min_face_detection_confidence=min_face_detection_confidence,
            min_face_presence_confidence=min_face_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_face_blendshapes=output_face_blendshapes,
        )
        landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        logger.info(
            "MediaPipe FaceLandmarker (Tasks API) initialised "
            "(mode=%s, num_faces=%s, blendshapes=%s, model=%s)",
            running_mode.name,
            num_faces,
            output_face_blendshapes,
            model_path,
        )
        return landmarker
    except Exception:  # noqa: BLE001
        logger.exception("Failed to create FaceLandmarker from Tasks API")
        return None


def to_mp_image(image_rgb):
    """Wrap an RGB numpy array in an ``mp.Image`` (SRGB format).

    Helper so call sites don't need ``import mediapipe`` just for the format
    enum. The caller is responsible for BGR→RGB conversion.
    """
    import mediapipe as mp

    return mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
