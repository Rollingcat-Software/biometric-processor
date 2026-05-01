"""Unit tests for YOLOCardTypeDetector — always-on OCR + borderline reject.

Mocks the YOLO model and Tesseract so the test does not require the model
weights, ONNX runtime, or a Tesseract install. Exercises three paths:

1. plain detection at high confidence (>=0.75) → returned as-is, no reject.
2. OCR-driven class switch (YOLO bbox vs OCR keyword evidence disagree).
3. borderline reject when YOLO confidence is below 0.75 and OCR produced
   no supporting keywords. Includes the case where OCR itself was
   unavailable (Tesseract missing/timeout) — that path must reject too,
   matching the `_ocr_validate` docstring contract.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.infrastructure.ml.card_type.yolo_card_type_detector import (
    YOLOCardTypeDetector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _box(class_id: int, confidence: float) -> SimpleNamespace:
    """Mimic an ultralytics Box object: `.cls[0]` and `.conf[0]`."""
    return SimpleNamespace(cls=[class_id], conf=[confidence])


def _yolo_result(boxes: list[SimpleNamespace]) -> SimpleNamespace:
    """Mimic an ultralytics Results object with `.boxes`."""
    return SimpleNamespace(boxes=boxes)


CLASS_NAMES = {
    0: "tc_kimlik",
    1: "ehliyet",
    2: "pasaport",
    3: "ogrenci_karti",
    4: "akademisyen_karti",
}


@pytest.fixture
def detector() -> YOLOCardTypeDetector:
    """A detector whose lazy-loaded model has been pre-stubbed.

    We bypass the real `_get_model()` (which would call ultralytics) by
    pre-assigning `_model` to a Mock with `.names` and a `__call__` that
    returns a list of result objects.
    """
    det = YOLOCardTypeDetector(model_path="unused.onnx", confidence_threshold=0.65)
    fake_model = MagicMock()
    fake_model.names = CLASS_NAMES
    det._model = fake_model
    return det


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_high_confidence_detection_returned_as_is(detector: YOLOCardTypeDetector):
    """confidence >= 0.75 + matching OCR keywords → detected, no reject."""
    detector._model.return_value = [_yolo_result([_box(0, 0.92)])]

    # OCR returns text containing TC Kimlik keywords → evidence='self'
    image = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch(
        "pytesseract.image_to_string",
        return_value="TURKIYE CUMHURIYETI KIMLIK NO 12345678901",
    ):
        result = detector.detect(image)

    assert result.detected is True
    assert result.class_name == "tc_kimlik"
    assert result.confidence == pytest.approx(0.92)


def test_ocr_drives_class_switch(detector: YOLOCardTypeDetector):
    """YOLO predicts ehliyet but OCR text screams ogrenci_karti → switch."""
    detector._model.return_value = [_yolo_result([_box(1, 0.80)])]  # ehliyet

    image = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch(
        "pytesseract.image_to_string",
        return_value="OGRENCI KIMLIK KARTI FAKULTE BOLUM OGR. NO 1234",
    ):
        result = detector.detect(image)

    assert result.detected is True
    # Class flipped to whichever has more keyword hits — ogrenci_karti.
    assert result.class_name == "ogrenci_karti"


def test_borderline_reject_when_no_ocr_evidence(detector: YOLOCardTypeDetector):
    """conf < 0.75 + OCR ran but no keyword hits → detected=False."""
    detector._model.return_value = [_yolo_result([_box(0, 0.70)])]

    image = np.zeros((640, 640, 3), dtype=np.uint8)
    # Random text with none of the keyword patterns.
    with patch("pytesseract.image_to_string", return_value="LOREM IPSUM DOLOR"):
        result = detector.detect(image)

    assert result.detected is False


def test_borderline_reject_when_ocr_unavailable(detector: YOLOCardTypeDetector):
    """conf < 0.75 + Tesseract import/timeout error → detected=False.

    Pre-fix this path returned `ocr_unavailable` and bypassed the
    borderline reject because the check only looked for `no_evidence`.
    """
    detector._model.return_value = [_yolo_result([_box(0, 0.70)])]

    image = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch(
        "pytesseract.image_to_string", side_effect=RuntimeError("tesseract missing")
    ):
        result = detector.detect(image)

    assert result.detected is False


def test_no_detection_when_below_confidence_threshold(detector: YOLOCardTypeDetector):
    """All raw detections below 0.65 → no_card path returns detected=False."""
    detector._model.return_value = [_yolo_result([_box(0, 0.30)])]

    image = np.zeros((640, 640, 3), dtype=np.uint8)
    result = detector.detect(image)

    assert result.detected is False


def test_supported_card_types_includes_akademisyen():
    """Class-level docstring fix sanity check: list MUST include akademisyen_karti."""
    det = YOLOCardTypeDetector(model_path="unused.onnx")
    assert "akademisyen_karti" in det.get_supported_card_types()
