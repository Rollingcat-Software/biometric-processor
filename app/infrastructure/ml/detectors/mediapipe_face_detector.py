"""MediaPipe Tasks API BlazeFace face detector implementation.

Fast, CPU-friendly face detector using MediaPipe's BlazeFace short-range model.
Handles faces rotated up to ~45° yaw — unlike OpenCV haar cascade which is
frontal-face only.

Performance (CPU-only server):
    - BlazeFace (this): 15–25ms
    - DeepFace/opencv:  80–300ms

Model:  blaze_face_short_range.tflite (float16, ~0.8MB)
Source: https://storage.googleapis.com/mediapipe-models/face_detector/
        blaze_face_short_range/float16/1/blaze_face_short_range.tflite
"""

import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.exceptions.face_errors import FaceNotDetectedError
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model download constants
# ---------------------------------------------------------------------------

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/"
    "blaze_face_short_range.tflite"
)

# Canonical cache location: <project_root>/app/core/models/
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[3] / "core" / "models" / "blaze_face_short_range.tflite"


def _ensure_model(model_path: Path) -> Path:
    """Download blaze_face_short_range.tflite if not already present.

    Args:
        model_path: Destination path for the .tflite file.

    Returns:
        model_path (unchanged) after ensuring the file exists.

    Raises:
        RuntimeError: If download fails and no local file is found.
    """
    if model_path.exists():
        return model_path

    model_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading BlazeFace model to {model_path} …")
    try:
        urllib.request.urlretrieve(_MODEL_URL, str(model_path))
        logger.info(f"BlazeFace model downloaded ({model_path.stat().st_size / 1024:.0f} KB)")
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download BlazeFace model from {_MODEL_URL}: {exc}"
        ) from exc

    return model_path


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class MediaPipeFaceDetector:
    """Face detector using MediaPipe Tasks API (BlazeFace short-range model).

    Implements the IFaceDetector protocol.  Uses a class-level singleton so
    the ~800KB TFLite model is loaded only once across requests.

    Features:
    - Detects faces rotated up to ±45° yaw (vs. frontal-only for opencv)
    - 15–25ms inference on CPU (vs. 80–300ms for DeepFace/opencv)
    - Auto-downloads model on first use; caches at app/core/models/
    - Falls back to DeepFaceDetector if MediaPipe is unavailable

    Configuration:
        min_detection_confidence (float): Minimum score to accept a detection
            (default: 0.5).  Set lower (e.g. 0.3) to catch more difficult
            angles at the cost of more false positives.
    """

    # Class-level singleton state
    _instance: Optional["MediaPipeFaceDetector"] = None
    _detector = None          # mediapipe FaceDetector (Tasks API)
    _mp = None                # mediapipe module reference
    _use_tasks: bool = False  # True when Tasks API is loaded

    def __new__(cls, min_detection_confidence: float = 0.5, model_path: Optional[Path] = None):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._min_detection_confidence = min_detection_confidence
            instance._model_path = model_path or _DEFAULT_MODEL_PATH
            cls._instance = instance
            cls._load_detector(instance)
        return cls._instance

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    def _load_detector(cls, instance: "MediaPipeFaceDetector") -> None:
        """Load MediaPipe Tasks API face detector (once per process)."""
        if cls._detector is not None:
            return

        t0 = time.perf_counter()
        try:
            import mediapipe as mp

            cls._mp = mp

            if not hasattr(mp, "tasks"):
                raise RuntimeError(
                    "mediapipe.tasks not available — upgrade to mediapipe>=0.10.0"
                )

            from mediapipe.tasks import python as tasks  # noqa: F401
            from mediapipe.tasks.python import vision

            model_path = _ensure_model(instance._model_path)

            opts = vision.FaceDetectorOptions(
                base_options=tasks.BaseOptions(model_asset_path=str(model_path)),
                min_detection_confidence=instance._min_detection_confidence,
            )
            cls._detector = vision.FaceDetector.create_from_options(opts)
            cls._use_tasks = True

            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                f"MediaPipe BlazeFace loaded in {elapsed_ms:.0f}ms "
                f"(model={model_path.name}, "
                f"confidence>={instance._min_detection_confidence})"
            )

        except Exception as exc:
            # Do not raise here — the factory will fall back to DeepFaceDetector.
            logger.warning(
                f"MediaPipe BlazeFace failed to load ({exc}). "
                "Detector will raise on first call so the factory can fall back."
            )
            cls._detector = None
            cls._use_tasks = False

    # ------------------------------------------------------------------
    # Public interface (matches IFaceDetector protocol)
    # ------------------------------------------------------------------

    def detect_sync(self, image: np.ndarray) -> FaceDetectionResult:
        """Synchronous face detection via BlazeFace.

        Args:
            image: BGR numpy array (H, W, C).

        Returns:
            FaceDetectionResult for the largest detected face.

        Raises:
            FaceNotDetectedError: When no face passes the confidence threshold.
            RuntimeError: If MediaPipe was not successfully loaded.
        """
        if self._detector is None or not self._use_tasks:
            raise RuntimeError(
                "MediaPipeFaceDetector is not available — MediaPipe failed to load at startup."
            )

        t0 = time.perf_counter()
        import mediapipe as mp

        h, w = image.shape[:2]
        rgb = image[:, :, ::-1].copy()  # BGR→RGB without relying on cv2 import
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        detection_result = self._detector.detect(mp_image)
        detections = detection_result.detections or []

        elapsed_ms = (time.perf_counter() - t0) * 1000
        _log = logger.info if settings.ENABLE_ML_PROFILER else logger.debug
        _log(f"Face detection: {elapsed_ms:.0f}ms, {len(detections)} faces found")

        if not detections:
            logger.warning("MediaPipe BlazeFace: no face detected")
            raise FaceNotDetectedError()

        # Pick the detection with the largest bounding-box area
        best = max(
            detections,
            key=lambda d: d.bounding_box.width * d.bounding_box.height,
        )

        if len(detections) > 1:
            logger.info(
                f"MediaPipe detected {len(detections)} faces — selecting largest"
            )

        bbox = best.bounding_box
        x = max(0, bbox.origin_x)
        y = max(0, bbox.origin_y)
        fw = min(bbox.width, w - x)
        fh = min(bbox.height, h - y)

        if fw <= 0 or fh <= 0:
            logger.warning(f"BlazeFace returned degenerate bbox: x={x} y={y} w={fw} h={fh}")
            raise FaceNotDetectedError()

        # BlazeFace categories list contains the detection score
        categories = best.categories
        confidence = float(categories[0].score) if categories else 0.9

        logger.info(
            f"Face detected (BlazeFace): bbox=({x},{y},{fw},{fh}), "
            f"confidence={confidence:.3f}, latency={elapsed_ms:.0f}ms"
        )

        return FaceDetectionResult(
            found=True,
            bounding_box=(x, y, fw, fh),
            landmarks=None,   # BlazeFace short-range provides 6 keypoints;
                              # we skip them — consumers use MediaPipe Face Mesh
                              # (mediapipe_landmarks.py) for full 468-point mesh.
            confidence=confidence,
            antispoof_score=None,
            antispoof_label=None,
        )

    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        """Async interface — delegates to detect_sync (BlazeFace is fast enough
        not to block the event loop significantly at 15–25ms, but callers using
        ASYNC_ML_ENABLED will wrap this in AsyncFaceDetector anyway).

        Args:
            image: BGR numpy array (H, W, C).

        Returns:
            FaceDetectionResult for the largest detected face.

        Raises:
            FaceNotDetectedError: When no face is found.
        """
        return self.detect_sync(image)

    def get_detector_name(self) -> str:
        """Return a human-readable backend identifier."""
        return "mediapipe_blazeface"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @classmethod
    def is_available(cls) -> bool:
        """Return True if the Tasks API detector loaded successfully."""
        return cls._detector is not None and cls._use_tasks

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state (test helper — do not call in production)."""
        cls._instance = None
        cls._detector = None
        cls._mp = None
        cls._use_tasks = False
