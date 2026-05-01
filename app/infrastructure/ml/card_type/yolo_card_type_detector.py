"""YOLO-based card type detector implementation."""

import logging
import os
import re
import time
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

# NOTE: a `_CONFUSABLE_PAIRS` constant used to live here, gating OCR
# validation to a small whitelist of confusable card-type pairs. OCR is
# now run on every detection (see `_ocr_validate` below), so the pair
# whitelist is gone.

# Sentinel values returned by `_ocr_validate` to signal that no OCR
# keyword evidence backs the YOLO class. Both should be treated identically
# by the borderline-reject path. `OCR_UNAVAILABLE` is reported when the
# OCR step itself failed (Tesseract missing/timeout); `NO_EVIDENCE` is
# reported when OCR ran but produced no matching keywords.
_OCR_NO_EVIDENCE: frozenset[str] = frozenset({"no_evidence", "ocr_unavailable"})

# Default model path relative to this file.
# best_fp16.onnx (FP16 ONNX, 50MB) is used instead of best.onnx (FP32, 103MB).
# FP16 on CPU has identical inference speed to FP32 but uses half the memory.
# Override via CARD_MODEL_PATH env var (filename only, not full path).
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "core" / "card_type_model" / os.getenv("CARD_MODEL_PATH", "best_fp16.onnx")


@lru_cache(maxsize=1)
def _get_yolo_model(model_path: str):
    """Load YOLO model with caching and ONNX Runtime warmup.

    Passes task='detect' explicitly so Ultralytics doesn't need to infer it from
    the file extension — required when loading .onnx exports.

    A dummy inference on a blank 640×640 image is run after loading to warm up
    ONNX Runtime session internals, so the first real request does not pay the
    cold-start cost (~several hundred ms on CPU).
    """
    from ultralytics import YOLO
    t0 = time.monotonic()
    logger.info(f"Loading YOLO model from: {model_path}")
    # task='detect' is required for .onnx; harmless for .pt
    model = YOLO(model_path, task="detect")
    # Warmup: one dummy inference on a blank 640×640 RGB image
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    model(dummy, conf=0.05, verbose=False)
    elapsed = (time.monotonic() - t0) * 1000
    logger.info(f"Card type model loaded and warmed up in {elapsed:.0f}ms")
    return model


class YOLOCardTypeDetector(ICardTypeDetector):
    """Card type detector using YOLO object detection.

    This implementation uses Ultralytics YOLO for detecting
    different types of identity cards in images.

    Supported Card Types:
    - tc_kimlik: Turkish National ID
    - ehliyet: Driver's License
    - pasaport: Passport
    - ogrenci_karti: Student Card
    - akademisyen_karti: Academic Staff Card
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.65,
    ) -> None:
        """Initialize YOLO card type detector.

        Args:
            model_path: Path to YOLO model weights. Uses default if not provided.
            confidence_threshold: Minimum confidence for detection (0.0 to 1.0).
                Default raised to 0.65 (was 0.5) per USER-BUG-2 — the small
                training dataset means confidence in [0.5, 0.65] frequently
                produced confidently-wrong calls. Borderline calls now fall
                through to "not detected" so the UI can prompt manual select.
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
        _t_infer = time.monotonic()
        raw_results = model(image, conf=0.05, verbose=False)
        raw_result = raw_results[0]
        logger.info(f"Card detection inference: {(time.monotonic() - _t_infer) * 1000:.0f}ms")

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

        # Always run OCR validation — not only for confusable pairs.
        # Per USER-BUG-2 the small dataset can hand back a confidently-wrong
        # class for any pair; OCR keyword evidence (when text is legible) is
        # a more reliable disambiguator than the YOLO confidence alone.
        corrected_name, ocr_evidence = self._ocr_validate(image, class_name)
        if corrected_name != class_name:
            logger.info(
                f"OCR corrected card type: {class_name} -> {corrected_name} "
                f"(YOLO confidence={confidence:.2f}, OCR evidence={ocr_evidence})"
            )
            class_name = corrected_name
            # Find corrected class_id
            for cid, name in model.names.items():
                if name == corrected_name:
                    class_id = cid
                    break

        # Reject borderline calls. If YOLO confidence is below 0.75 AND OCR
        # produced no supporting evidence for the class (either no keyword
        # hits OR OCR itself was unavailable), the call is likely a guess —
        # return detected=False so the UI prompts manual select rather than
        # committing to the wrong class. Both `no_evidence` and
        # `ocr_unavailable` are treated identically per the `_ocr_validate`
        # docstring.
        if confidence < 0.75 and ocr_evidence in _OCR_NO_EVIDENCE:
            logger.info(
                f"Rejecting borderline detection: class={class_name}, "
                f"confidence={confidence:.2f}, OCR found no supporting keywords"
            )
            return CardTypeResult(detected=False)

        logger.info(
            f"Card detected: {class_name} (id={class_id}, confidence={confidence:.2f}, "
            f"OCR evidence={ocr_evidence})"
        )

        return CardTypeResult(
            detected=True,
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
        )

    def _ocr_validate(
        self, image: np.ndarray, yolo_class: str
    ) -> tuple[str, str]:
        """Use OCR to validate or correct the YOLO classification.

        Runs OCR on every detection (not just confusable pairs). When the
        OCR text contains keywords that point to a different supported
        class than YOLO's pick, returns the OCR-preferred class. Otherwise
        returns the YOLO class.

        Returns:
            (chosen_class, evidence) — evidence is one of:
              * "self"          → OCR keywords match the YOLO class
              * "switched_to_X" → OCR keywords for X dominated; class was switched
              * "no_evidence"   → OCR ran but no class accumulated keyword hits
              * "ocr_unavailable" → OCR step itself failed (treated as no_evidence)
        """
        # Run OCR on the image
        try:
            import pytesseract
            pil_image = Image.fromarray(image)
            raw_text = pytesseract.image_to_string(
                pil_image, lang="tur+eng", timeout=5
            ).upper()
        except Exception as e:
            logger.debug(f"OCR validation skipped: {e}")
            return yolo_class, "ocr_unavailable"

        if not raw_text.strip():
            return yolo_class, "no_evidence"

        # Count keyword matches for every supported class
        def count_matches(card_type: str) -> int:
            patterns = _CARD_TYPE_KEYWORDS.get(card_type, [])
            return sum(1 for p in patterns if re.search(p, raw_text, re.IGNORECASE))

        scores = {
            cls: count_matches(cls) for cls in _CARD_TYPE_KEYWORDS.keys()
        }

        if all(s == 0 for s in scores.values()):
            return yolo_class, "no_evidence"

        # Best OCR-supported class
        best_class, best_score = max(scores.items(), key=lambda kv: kv[1])
        yolo_score = scores.get(yolo_class, 0)

        logger.debug(
            f"OCR validation: yolo={yolo_class}(score={yolo_score}), "
            f"best={best_class}(score={best_score}), all={scores}, "
            f"text_preview={raw_text[:100]!r}"
        )

        # Only override if OCR strictly prefers a different class.
        # Equality keeps YOLO's pick — single-keyword ties shouldn't flip
        # a confident bbox-based call.
        if best_score > yolo_score:
            return best_class, f"switched_to_{best_class}"

        if yolo_score > 0:
            return yolo_class, "self"

        return yolo_class, "no_evidence"

    def get_supported_card_types(self) -> list[str]:
        """Get list of card types this detector can identify.

        Returns:
            List of supported card type names
        """
        return ["tc_kimlik", "ehliyet", "pasaport", "ogrenci_karti", "akademisyen_karti"]

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
