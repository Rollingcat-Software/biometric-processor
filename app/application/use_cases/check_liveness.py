"""Liveness check use case."""

import logging
import cv2

from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.entities.liveness_result import LivenessResult

logger = logging.getLogger(__name__)


class CheckLivenessUseCase:
    """Use case for checking liveness of a face.

    This use case orchestrates the following steps:
    1. Detect face in image
    2. Perform liveness check

    Following Single Responsibility Principle: Only handles liveness check orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).

    Note:
        Currently uses StubLivenessDetector which always passes.
        Will be updated in Sprint 3 with real smile/blink detection.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        liveness_detector: ILivenessDetector,
    ) -> None:
        """Initialize liveness check use case.

        Args:
            detector: Face detector implementation
            liveness_detector: Liveness detector implementation
        """
        self._detector = detector
        self._liveness_detector = liveness_detector

        logger.info("CheckLivenessUseCase initialized")

    async def execute(self, image_path: str) -> LivenessResult:
        """Execute liveness check.

        Args:
            image_path: Path to image file

        Returns:
            LivenessResult with liveness check outcome

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            LivenessCheckError: When liveness check fails
        """
        logger.info("Starting liveness check")

        # Step 1: Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Step 2: Detect face (to ensure there's a face before liveness check)
        logger.debug("Step 1/2: Detecting face...")
        detection = await self._detector.detect(image)

        logger.debug(f"Face detected with confidence: {detection.confidence:.2f}")

        # Step 3: Perform liveness check
        logger.debug("Step 2/2: Checking liveness...")
        liveness_result = await self._liveness_detector.check_liveness(image)

        logger.info(
            f"Liveness check completed: "
            f"is_live={liveness_result.is_live}, "
            f"score={liveness_result.liveness_score:.1f}, "
            f"challenge={liveness_result.challenge}"
        )

        return liveness_result
