"""YOLO-based card type detector implementation."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

from app.domain.entities.card_type_result import CardTypeResult
from app.domain.interfaces.card_type_detector import ICardTypeDetector

logger = logging.getLogger(__name__)

# Default model path relative to this file
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "core" / "card_type_model" / "best.pt"


@lru_cache(maxsize=1)
def _get_yolo_model(model_path: str):
    """Load YOLO model with caching."""
    from ultralytics import YOLO
    logger.info(f"Loading YOLO model from: {model_path}")
    return YOLO(model_path)


class YOLOCardTypeDetector(ICardTypeDetector):
    """Card type detector using YOLO object detection.

    This implementation uses Ultralytics YOLO for detecting
    different types of identity cards in images.

    Supported Card Types:
    - tc_kimlik: Turkish National ID
    - ehliyet: Driver's License
    - pasaport: Passport
    - ogrenci_karti: Student Card
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize YOLO card type detector.

        Args:
            model_path: Path to YOLO model weights. Uses default if not provided.
            confidence_threshold: Minimum confidence for detection (0.0 to 1.0)
        """
        self._model_path = model_path or str(DEFAULT_MODEL_PATH)
        self._confidence_threshold = confidence_threshold
        self._model = None

        logger.info(
            f"YOLOCardTypeDetector initialized: "
            f"model={self._model_path}, threshold={confidence_threshold}"
        )

    def _get_model(self):
        """Lazy load the YOLO model."""
        if self._model is None:
            self._model = _get_yolo_model(self._model_path)
        return self._model

    def detect(self, image: np.ndarray) -> CardTypeResult:
        """Detect card type in image.

        Args:
            image: Input image as numpy array (H, W, C) in RGB format

        Returns:
            CardTypeResult containing detection information
        """
        logger.debug("Starting card type detection")

        model = self._get_model()
        results = model(image, conf=self._confidence_threshold, verbose=False)
        result = results[0]

        if len(result.boxes) == 0:
            logger.debug("No card detected in image")
            return CardTypeResult(detected=False)

        # Get the detection with highest confidence
        best_box = max(result.boxes, key=lambda b: float(b.conf[0]))
        class_id = int(best_box.cls[0])
        confidence = float(best_box.conf[0])
        class_name = model.names[class_id]

        logger.info(
            f"Card detected: {class_name} (id={class_id}, confidence={confidence:.2f})"
        )

        return CardTypeResult(
            detected=True,
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
        )

    def get_supported_card_types(self) -> list[str]:
        """Get list of card types this detector can identify.

        Returns:
            List of supported card type names
        """
        return ["tc_kimlik", "ehliyet", "pasaport", "ogrenci_karti"]

    def get_confidence_threshold(self) -> float:
        """Get the minimum confidence threshold for detection.

        Returns:
            Confidence threshold (0.0 to 1.0)
        """
        return self._confidence_threshold

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the minimum confidence threshold for detection.

        Args:
            threshold: New threshold value (0.0 to 1.0)

        Raises:
            ValueError: If threshold is out of range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")
        self._confidence_threshold = threshold
        logger.info(f"Confidence threshold updated to {threshold}")
