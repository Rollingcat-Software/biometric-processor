"""Unit tests for DeepFace face-detector post-filtering.

The pure post-filter geometry (``_is_nested_false_positive``) is a static method
with no TensorFlow/DeepFace dependency, so these assertions run in the lint/unit
CI image where TensorFlow is not installed. The ``DeepFaceDetector`` module now
imports DeepFace lazily (inside ``_extract_faces``), so importing the class for
these tests does NOT pull in TensorFlow.

The single TF-dependent test (real ``detect`` call) is gated behind
``@pytest.mark.skipif`` on TensorFlow availability so it is skipped — not
failed — in the lightweight CI image, while still being exercised inside the
Docker ML stack where TensorFlow + DeepFace weights are present.
"""

import importlib.util

import numpy as np
import pytest

from app.infrastructure.ml.detectors.deepface_detector import DeepFaceDetector

# DeepFace imports TensorFlow at module load; both must be importable for the
# real-detection test to run. We probe for the spec rather than importing to
# keep collection cheap.
_TF_AVAILABLE = (
    importlib.util.find_spec("tensorflow") is not None
    and importlib.util.find_spec("deepface") is not None
)


# ---------------------------------------------------------------------------
# Pure-logic assertions (no TensorFlow) — always run in CI.
# ---------------------------------------------------------------------------


def test_nested_false_positive_filters_mouth_like_candidate_inside_primary_face():
    primary = (200, 120, 220, 240)
    mouth_like = (255, 255, 90, 72)

    assert DeepFaceDetector._is_nested_false_positive(mouth_like, primary) is True


def test_nested_false_positive_keeps_separate_second_face_candidate():
    primary = (200, 120, 220, 240)
    separate_face = (28, 96, 140, 150)

    assert DeepFaceDetector._is_nested_false_positive(separate_face, primary) is False


def test_nested_false_positive_small_fully_covered_candidate_is_filtered():
    # Candidate almost entirely inside the primary face and small relative to
    # it (>=78% covered, <=45% area) → treated as a nested false positive.
    primary = (100, 100, 200, 200)
    inner = (150, 150, 60, 60)

    assert DeepFaceDetector._is_nested_false_positive(inner, primary) is True


def test_nested_false_positive_large_overlapping_candidate_is_kept():
    # A candidate larger than 45% of the primary area is not small-relative, so
    # it should be kept even though it overlaps.
    primary = (100, 100, 200, 200)
    large_overlap = (120, 120, 180, 180)

    assert DeepFaceDetector._is_nested_false_positive(large_overlap, primary) is False


def test_nested_false_positive_lower_face_mouth_region_is_filtered():
    # A small candidate centred in the lower 52% of the face with modest primary
    # coverage (mouth-like) is filtered via the lower-face-region branch.
    primary = (100, 100, 200, 200)
    mouth = (160, 230, 70, 50)

    assert DeepFaceDetector._is_nested_false_positive(mouth, primary) is True


def test_nested_false_positive_handles_zero_area_bbox_without_error():
    primary = (100, 100, 200, 200)
    degenerate = (150, 150, 0, 0)

    # max(area, 1) guards against division by zero; result must be a bool.
    result = DeepFaceDetector._is_nested_false_positive(degenerate, primary)
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# TensorFlow-dependent test — skipped (not failed) when TF is unavailable.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(
    not _TF_AVAILABLE,
    reason="TensorFlow/DeepFace not installed (runs only in the Docker ML stack)",
)
def test_detect_raises_face_not_detected_on_blank_image():
    """The real detection path must reject an image with no detectable face.

    This exercises the lazy ``from deepface import DeepFace`` import inside
    ``_extract_faces`` plus the enforce_detection=True error mapping. It only
    runs where TensorFlow + DeepFace weights are present.
    """
    import asyncio

    from app.domain.exceptions.face_errors import FaceNotDetectedError

    detector = DeepFaceDetector(detector_backend="opencv", anti_spoofing=False)
    blank = np.zeros((128, 128, 3), dtype=np.uint8)

    with pytest.raises(FaceNotDetectedError):
        asyncio.run(detector.detect(blank))
