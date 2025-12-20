"""Detect facial landmarks use case."""

import logging

import numpy as np

from app.domain.entities.face_landmarks import LandmarkResult
from app.domain.exceptions.face_errors import FaceNotFoundError
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.landmark_detector import ILandmarkDetector

logger = logging.getLogger(__name__)


class DetectLandmarksUseCase:
    """Use case for detecting facial landmarks.

    Detects detailed facial landmarks (68 or 468 points)
    and estimates head pose.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        landmark_detector: ILandmarkDetector,
    ) -> None:
        """Initialize landmark detection use case.

        Args:
            detector: Face detector implementation
            landmark_detector: Landmark detector implementation
        """
        self._detector = detector
        self._landmark_detector = landmark_detector
        logger.info("DetectLandmarksUseCase initialized")

    async def execute(
        self, image: np.ndarray, include_3d: bool = False
    ) -> LandmarkResult:
        """Execute landmark detection.

        Args:
            image: Input image as numpy array (RGB format)
            include_3d: Whether to include 3D coordinates

        Returns:
            LandmarkResult with detected landmarks

        Raises:
            FaceNotFoundError: When no face is detected
        """
        logger.info(f"Starting landmark detection (include_3d={include_3d})")

        # Detect face first to validate
        detection_result = await self._detector.detect(image)
        if not detection_result.found:
            raise FaceNotFoundError("No face detected in image")

        # Detect landmarks
        result = self._landmark_detector.detect(image, include_3d=include_3d)

        logger.info(
            f"Landmark detection complete: "
            f"model={result.model}, landmarks={result.landmark_count}"
        )

        return result
