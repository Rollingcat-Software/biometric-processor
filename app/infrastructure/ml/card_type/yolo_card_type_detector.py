"""YOLO-based card type detector implementation."""

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from app.domain.entities.card_type_result import CardTypeResult
from app.domain.interfaces.card_type_detector import ICardTypeDetector

logger = logging.getLogger(__name__)

# OCR keywords for disambiguating confusable card types
_CARD_TYPE_KEYWORDS: dict[str, list[str]] = {
    "tc_kimlik": [
        r"T\.?C\.?\s*K[İI]ML[İI]K",
        r"N[ÜU]FUS\s*C[ÜU]ZDAN",
        r"REPUBLIC\s*OF\s*TURKEY",
        r"T[ÜU]RK[İI]YE\s*CUMHUR[İI]YET[İI]",
        r"K[İI]ML[İI]K\s*NO",
        r"IDENTITY\s*CARD",
    ],
    "ehliyet": [
        r"S[ÜU]R[ÜU]C[ÜU]\s*BELGES[İI]",
        r"DRIVING\s*LIC[EA]N[SC]E",
        r"PERMIS\s*DE\s*CONDUIRE",
        r"S[ÜU]R[ÜU]C[ÜU]L[ÜU]K",
    ],
    "ogrenci_karti": [
        r"[ÖO](?:[GĞ])RENC[İI]",
        r"STUDENT",
        r"[ÖO](?:[GĞ])R\.\s*NO",
        r"FACULTY|FAK[ÜU]LTE",
        r"B[ÖO]L[ÜU]M",
    ],
    "akademisyen_karti": [
        r"AKADEM[İI]SYEN",
        r"ACADEMIC",
        r"[ÖO](?:[GĞ])RET[İI]M\s*[ÜU]YES[İI]",
        r"PROF|DO[CÇ]|DR\.",
    ],
    "pasaport": [
        r"PASAPORT",
        r"PASSPORT",
    ],
}

# Pairs that are commonly confused — OCR validation triggers for these
_CONFUSABLE_PAIRS: set[frozenset[str]] = {
    frozenset({"ogrenci_karti", "akademisyen_karti"}),
    frozenset({"tc_kimlik", "ehliyet"}),
}

# Default model path relative to this file.
# best.onnx (FP32 ONNX) is used instead of best.pt because Ultralytics+ONNX Runtime
# is ~2.7x faster on CPU (avg 1,775ms vs 4,781ms) with identical class names and accuracy.
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "core" / "card_type_model" / "best.onnx"


@lru_cache(maxsize=1)
def _get_yolo_model(model_path: str):
    """Load YOLO model with caching.

    Passes task='detect' explicitly so Ultralytics doesn't need to infer it from
    the file extension — required when loading .onnx exports.
    """
    from ultralytics import YOLO
    logger.info(f"Loading YOLO model from: {model_path}")
    # task='detect' is required for .onnx; harmless for .pt
    return YOLO(model_path, task="detect")


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

        # Run inference at a low conf floor so we can log ALL raw detections
        raw_results = model(image, conf=0.05, verbose=False)
        raw_result = raw_results[0]

        # Log every detection the model produces (diagnostic)
        for box in raw_result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            logger.info(f"YOLO raw detections: {model.names[cls_id]}={conf:.3f}")

        # Apply the configured confidence threshold
        filtered_boxes = [
            b for b in raw_result.boxes
            if float(b.conf[0]) >= self._confidence_threshold
        ]

        if len(filtered_boxes) == 0:
            logger.debug("No card detected in image above threshold %.2f", self._confidence_threshold)
            return CardTypeResult(detected=False)

        # Get the detection with highest confidence
        best_box = max(filtered_boxes, key=lambda b: float(b.conf[0]))
        class_id = int(best_box.cls[0])
        confidence = float(best_box.conf[0])
        class_name = model.names[class_id]

        # Check if the detected class is in a confusable pair — validate with OCR
        corrected_name = self._ocr_validate(image, class_name, confidence)
        if corrected_name != class_name:
            logger.info(
                f"OCR corrected card type: {class_name} -> {corrected_name} "
                f"(YOLO confidence={confidence:.2f})"
            )
            class_name = corrected_name
            # Find corrected class_id
            for cid, name in model.names.items():
                if name == corrected_name:
                    class_id = cid
                    break

        logger.info(
            f"Card detected: {class_name} (id={class_id}, confidence={confidence:.2f})"
        )

        return CardTypeResult(
            detected=True,
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
        )

    def _ocr_validate(
        self, image: np.ndarray, yolo_class: str, confidence: float
    ) -> str:
        """Use OCR to validate or correct YOLO classification for confusable pairs.

        Only runs when the YOLO prediction is in a known confusable pair
        (e.g. tc_kimlik/ehliyet, ogrenci_karti/akademisyen_karti).
        Returns corrected class name or the original if OCR can't determine.
        """
        # Find if yolo_class belongs to a confusable pair
        confusable_partner: Optional[str] = None
        for pair in _CONFUSABLE_PAIRS:
            if yolo_class in pair:
                confusable_partner = next(iter(pair - frozenset({yolo_class})))
                break

        if confusable_partner is None:
            return yolo_class

        # Run OCR on the image
        try:
            import pytesseract
            pil_image = Image.fromarray(image)
            raw_text = pytesseract.image_to_string(
                pil_image, lang="tur+eng", timeout=5
            ).upper()
        except Exception as e:
            logger.debug(f"OCR validation skipped: {e}")
            return yolo_class

        if not raw_text.strip():
            return yolo_class

        # Count keyword matches for both the YOLO class and its confusable partner
        def count_matches(card_type: str) -> int:
            patterns = _CARD_TYPE_KEYWORDS.get(card_type, [])
            return sum(1 for p in patterns if re.search(p, raw_text, re.IGNORECASE))

        yolo_matches = count_matches(yolo_class)
        partner_matches = count_matches(confusable_partner)

        logger.debug(
            f"OCR validation: yolo={yolo_class}({yolo_matches} matches), "
            f"partner={confusable_partner}({partner_matches} matches), "
            f"text_preview={raw_text[:100]!r}"
        )

        # Only override if the partner has strictly more keyword matches
        if partner_matches > yolo_matches:
            return confusable_partner

        return yolo_class

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
