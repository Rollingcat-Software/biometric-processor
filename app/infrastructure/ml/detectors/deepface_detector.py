"""DeepFace-based face detector implementation."""

import logging
from typing import Optional, Tuple

import numpy as np
from deepface import DeepFace

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.exceptions.face_errors import FaceNotDetectedError, MultipleFacesError
from app.domain.interfaces.face_detector import IFaceDetector

logger = logging.getLogger(__name__)


class DeepFaceDetector:
    """Face detector using DeepFace library.

    Implements IFaceDetector interface using DeepFace's face detection.
    Supports multiple detection backends (opencv, ssd, mtcnn, retinaface, mediapipe).

    Following Open/Closed Principle: Can be replaced with different detector
    without changing client code.
    """

    def __init__(self, detector_backend: str = "opencv", align: bool = True) -> None:
        """Initialize DeepFace detector.

        Args:
            detector_backend: Detection backend to use
                Options: "opencv", "ssd", "mtcnn", "retinaface", "mediapipe", "yolov8"
            align: Whether to align detected faces

        Note:
            - opencv: Fast but less accurate
            - mtcnn: Good balance of speed and accuracy
            - retinaface: Most accurate but slower
        """
        self._detector_backend = detector_backend
        self._align = align

        logger.info(
            f"Initialized DeepFaceDetector with backend: {detector_backend}, align: {align}"
        )

    def detect_sync(self, image: np.ndarray) -> FaceDetectionResult:
        """Synchronous face detection for thread pool execution.

        This method contains the actual blocking DeepFace call.
        Called by AsyncFaceDetector via thread pool for non-blocking execution.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            FaceDetectionResult with detection information

        Raises:
            FaceNotDetectedError: When no face is detected
            MultipleFacesError: When multiple faces are detected
        """
        try:
            # Extract faces using DeepFace (blocking operation)
            face_objs = DeepFace.extract_faces(
                img_path=image,
                detector_backend=self._detector_backend,
                enforce_detection=True,
                align=self._align,
            )

            if not face_objs or len(face_objs) == 0:
                logger.warning("No face detected in image")
                raise FaceNotDetectedError()

            if len(face_objs) > 1:
                logger.warning(f"Multiple faces detected: {len(face_objs)}")
                raise MultipleFacesError(count=len(face_objs))

            # Get the detected face
            face_obj = face_objs[0]

            # Extract facial area (bounding box)
            facial_area = face_obj.get("facial_area", {})
            x = facial_area.get("x", 0)
            y = facial_area.get("y", 0)
            w = facial_area.get("w", 0)
            h = facial_area.get("h", 0)

            bounding_box: Optional[Tuple[int, int, int, int]] = (x, y, w, h)

            # Extract confidence
            confidence = float(face_obj.get("confidence", 0.99))

            # Landmarks (not provided by all backends)
            landmarks = None  # DeepFace doesn't expose landmarks in extract_faces

            logger.info(
                f"Face detected successfully: bbox=({x},{y},{w},{h}), confidence={confidence:.2f}"
            )

            return FaceDetectionResult(
                found=True,
                bounding_box=bounding_box,
                landmarks=landmarks,
                confidence=confidence,
            )

        except ValueError as e:
            # DeepFace raises ValueError when no face is detected
            if "Face could not be detected" in str(e) or "no face" in str(e).lower():
                logger.warning(f"No face detected: {e}")
                raise FaceNotDetectedError()
            else:
                logger.error(f"Face detection error: {e}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Unexpected error during face detection: {e}", exc_info=True)
            raise

    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect face in image (async wrapper).

        This method delegates to detect_sync for backward compatibility.
        For truly non-blocking execution, use AsyncFaceDetector wrapper.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            FaceDetectionResult with detection information

        Raises:
            FaceNotDetectedError: When no face is detected
            MultipleFacesError: When multiple faces are detected
        """
        return self.detect_sync(image)

    def get_detector_name(self) -> str:
        """Get the name of the detector backend.

        Returns:
            Detector backend name
        """
        return self._detector_backend
