"""Card type detector interface."""

from typing import Protocol

import numpy as np

from app.domain.entities.card_type_result import CardTypeResult


class ICardTypeDetector(Protocol):
    """Protocol for card type detection implementations.

    Implementations can use different techniques (YOLO, CNN, etc.)
    without changing client code (Open/Closed Principle).
    """

    def detect(self, image: np.ndarray) -> CardTypeResult:
        """Detect card type in image.

        Args:
            image: Input image as numpy array (H, W, C) in RGB format

        Returns:
            CardTypeResult containing detection information

        Note:
            The specific model and technique depends on implementation.
        """
        ...

    def get_supported_card_types(self) -> list[str]:
        """Get list of card types this detector can identify.

        Returns:
            List of supported card type names
        """
        ...

    def get_confidence_threshold(self) -> float:
        """Get the minimum confidence threshold for detection.

        Returns:
            Confidence threshold (0.0 to 1.0)
        """
        ...
