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

        # Validate that a face exists first (quick check)
        detection_result = await self._detector.detect(image)
        if not detection_result.found:
            raise FaceNotFoundError("No face detected in image")

        # IMPORTANT: Don't crop the face before demographics analysis!
        # Cropping can degrade image quality and reduce resolution below optimal 224x224.
        # DeepFace.analyze() handles face detection internally and performs better
        # with the full image rather than a pre-cropped face region.
        #
        # Research shows DeepFace performs best at 224x224 resolution.
        # Cropping a small face from a larger image can result in a face region
        # smaller than 224x224, significantly degrading accuracy (MAE increases).
        #
        # Therefore, we send the full image to the demographics analyzer.
        result = self._demographics_analyzer.analyze(image)

        logger.info(
            f"Demographics analysis complete: "
            f"age={result.age.value} (±{(result.age.range[1] - result.age.value)} years, "
            f"confidence={result.age.confidence:.2f}), "
            f"gender={result.gender.value} (confidence={result.gender.confidence:.2f})"
        )

        return result
