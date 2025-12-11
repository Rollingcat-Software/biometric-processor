"""Analyze demographics use case."""

import logging

import numpy as np

from app.domain.entities.demographics import DemographicsResult
from app.domain.exceptions.face_errors import FaceNotFoundError
from app.domain.interfaces.demographics_analyzer import IDemographicsAnalyzer
from app.domain.interfaces.face_detector import IFaceDetector

logger = logging.getLogger(__name__)


class AnalyzeDemographicsUseCase:
    """Use case for analyzing face demographics.

    Estimates age, gender, and optionally race and emotion
    from a face image.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        demographics_analyzer: IDemographicsAnalyzer,
    ) -> None:
        """Initialize demographics analysis use case.

        Args:
            detector: Face detector implementation
            demographics_analyzer: Demographics analyzer implementation
        """
        self._detector = detector
        self._demographics_analyzer = demographics_analyzer
        logger.info("AnalyzeDemographicsUseCase initialized")

    async def execute(self, image: np.ndarray) -> DemographicsResult:
        """Execute demographics analysis.

        Args:
            image: Input image as numpy array (RGB format)

        Returns:
            DemographicsResult with age, gender, and optional attributes

        Raises:
            FaceNotFoundError: When no face is detected
        """
        logger.info("Starting demographics analysis")

        # Detect face first
        detection_result = self._detector.detect(image)
        if not detection_result.face_detected:
            raise FaceNotFoundError("No face detected in image")

        # Extract face region
        if detection_result.face_coordinates:
            x, y, w, h = detection_result.face_coordinates
            face_image = image[y : y + h, x : x + w]
        else:
            face_image = image

        # Analyze demographics
        result = self._demographics_analyzer.analyze(face_image)

        logger.info(
            f"Demographics analysis complete: "
            f"age={result.age.value}, gender={result.gender.value}"
        )

        return result
