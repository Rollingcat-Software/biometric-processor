"""Decode a probe image and detect its face once, for every use case in a request.

The image ``/verify`` route runs passive liveness and then embedding
verification on the same upload with the same detector singleton. Detection
(MTCNN plus the detector's anti-spoof model in production) is the most
expensive shared step, so it runs once here and the result is handed to both
use cases instead of being recomputed.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import cv2
import numpy as np

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.interfaces.face_detector import IFaceDetector


@dataclass(frozen=True)
class DetectedFaceImage:
    """A decoded probe image and its single face detection.

    ``image`` is read-only so no consumer can change the pixels another one
    sees; a consumer that needs a writable array takes ``fresh_image()``,
    which is what a separate decode used to give it.
    """

    image: np.ndarray
    detection: FaceDetectionResult
    decode_ms: float
    detect_ms: float

    def fresh_image(self) -> np.ndarray:
        """A writable copy of the decoded pixels, private to the caller."""
        return self.image.copy()


async def decode_image(image_path: str) -> np.ndarray:
    """Read an image file as BGR off the event loop.

    Raises:
        ValueError: When the file cannot be decoded.
    """
    image = await asyncio.to_thread(cv2.imread, image_path)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    return image


async def detect_face_image(detector: IFaceDetector, image_path: str) -> DetectedFaceImage:
    """Decode ``image_path`` and run ``detector`` on it exactly once.

    Errors from the detector (no face, several faces, anti-spoof model load
    failure) propagate unchanged so each caller keeps its own handling.
    """
    t0 = time.perf_counter()
    image = await decode_image(image_path)
    decode_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    detection = await detector.detect(image)
    detect_ms = (time.perf_counter() - t0) * 1000

    image.setflags(write=False)
    return DetectedFaceImage(
        image=image,
        detection=detection,
        decode_ms=decode_ms,
        detect_ms=detect_ms,
    )
