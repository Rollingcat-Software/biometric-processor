"""Card type detection use case."""

import logging

import cv2
import numpy as np

from app.domain.entities.card_type_result import CardTypeResult
from app.domain.interfaces.card_type_detector import ICardTypeDetector

logger = logging.getLogger(__name__)


class DetectCardTypeUseCase:
    """Use case for detecting card type in images.

    This use case orchestrates card type detection using
    the injected detector implementation.

    Following Single Responsibility Principle: Only handles card type detection orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    def __init__(self, detector: ICardTypeDetector) -> None:
        """Initialize card type detection use case.

        Args:
            detector: Card type detector implementation
        """
        self._detector = detector
        logger.info("DetectCardTypeUseCase initialized")

    async def execute(self, image_path: str) -> CardTypeResult:
        """Execute card type detection.

        Args:
            image_path: Path to image file

        Returns:
            CardTypeResult with detection information

        Raises:
            ValueError: When image cannot be loaded
        """
        logger.info("Starting card type detection")

        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Detect card type
        result = self._detector.detect(image_rgb)

        logger.info(
            f"Card type detection completed: "
            f"detected={result.detected}, "
            f"class={result.class_name}, "
            f"confidence={result.confidence}"
        )

        return result

    async def execute_from_array(self, image: np.ndarray) -> CardTypeResult:
        """Execute card type detection from numpy array.

        Args:
            image: Image as numpy array (RGB format)

        Returns:
            CardTypeResult with detection information
        """
        logger.info("Starting card type detection from array")

        result = self._detector.detect(image)

        logger.info(
            f"Card type detection completed: "
            f"detected={result.detected}, "
            f"class={result.class_name}, "
            f"confidence={result.confidence}"
        )

        return result
