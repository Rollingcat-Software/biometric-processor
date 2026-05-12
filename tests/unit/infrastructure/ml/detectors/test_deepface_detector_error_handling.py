"""Regression tests for DeepFace ValueError discrimination.

Background — 2026-05-12 compound liveness bug:
    DeepFace 0.0.98 raises plain ``ValueError`` for two unrelated conditions:

      1. Real spoof verdict — ``SpoofDetected("Spoof detected in given image.")``
         from ``deepface/modules/exceptions.py``.
      2. Model-download failure — raised from
         ``deepface/commons/weight_utils.py:62``. Message contains the
         cracked-chain emoji "⛓️‍💥", the substring "downloading", and the
         URL fragment "anti_spoof_models/..." — which itself contains the
         substring "spoof".

    The previous error handler matched on ``"spoof" in err_str``, which
    routed BOTH conditions into the spoof-fallback path. That silently
    tagged every user as ``antispoof_label="spoof"`` whenever the model
    weights weren't already in the on-disk cache — bricking ``/verify``
    for every user (5 consecutive rejections for ``ff000003-...`` were
    the live evidence). These tests pin the discrimination so a
    regression fails loud.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.exceptions.face_errors import FaceNotDetectedError
from app.domain.exceptions.liveness_errors import LivenessModelLoadError
from app.infrastructure.ml.detectors.deepface_detector import DeepFaceDetector


def _dummy_image() -> np.ndarray:
    """200x200 BGR placeholder; bypassed by patching ``_extract_faces``."""
    return np.full((200, 200, 3), 128, dtype=np.uint8)


def _build_detector(anti_spoofing: bool = True) -> DeepFaceDetector:
    return DeepFaceDetector(
        detector_backend="opencv",
        align=False,
        anti_spoofing=anti_spoofing,
        anti_spoofing_threshold=0.5,
    )


def test_spoof_verdict_value_error_routes_into_fallback() -> None:
    """A genuine ``SpoofDetected`` ValueError must trigger the spoof
    fallback that returns ``antispoof_label="spoof"`` and carries fallback
    metadata in ``details``."""

    detector = _build_detector()
    # On the first call DeepFace raises a SpoofDetected ValueError; on the
    # fallback pass it returns a clean face object so the fallback can
    # produce a FaceDetectionResult.
    call_count = {"n": 0}

    def fake_extract_faces(image, anti_spoofing):  # noqa: ARG001
        call_count["n"] += 1
        if call_count["n"] == 1:
            assert anti_spoofing is True
            raise ValueError("Spoof detected in given image.")
        assert anti_spoofing is False
        return [
            {
                "facial_area": {"x": 10, "y": 10, "w": 100, "h": 100},
                "confidence": 0.9,
            }
        ]

    with patch.object(detector, "_extract_faces", side_effect=fake_extract_faces):
        result = detector.detect_sync(_dummy_image())

    assert isinstance(result, FaceDetectionResult)
    assert result.found is True
    assert result.antispoof_label == "spoof"
    assert result.antispoof_score == 1.0
    assert result.details is not None
    assert result.details.get("fallback_triggered") is True
    assert result.details.get("fallback_reason") == "deepface_spoof_exception"
    assert "Spoof detected" in result.details.get("fallback_exception_message", "")


def test_model_download_value_error_raises_liveness_model_load_error() -> None:
    """A DeepFace weight-download failure must raise the typed
    ``LivenessModelLoadError`` rather than silently producing
    ``antispoof_label="spoof"``."""

    detector = _build_detector()
    # The exact DeepFace 0.0.98 message — verified by reading
    # ``deepface/commons/weight_utils.py:62``.
    download_error_message = (
        "⛓️‍💥 An exception occurred while downloading 2.7_80x80_MiniFASNetV2.pth "
        "from https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/"
        "resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth. "
        "Consider downloading it manually to /root/.deepface/weights/2.7_80x80_MiniFASNetV2.pth."
    )

    def fake_extract_faces(image, anti_spoofing):  # noqa: ARG001
        raise ValueError(download_error_message)

    with patch.object(detector, "_extract_faces", side_effect=fake_extract_faces):
        with pytest.raises(LivenessModelLoadError) as exc_info:
            detector.detect_sync(_dummy_image())

    exc = exc_info.value
    assert "MiniFASNet" in exc.model_name or "MiniFASNetV2" in exc.model_name
    assert exc.target_path is not None
    assert "2.7_80x80_MiniFASNetV2.pth" in exc.target_path
    assert exc.cause is not None
    assert "downloading" in exc.cause.lower()
    # Critical regression: the message contains the substring "spoof"
    # (via "anti_spoof_models" URL fragment) but must NOT be silently
    # routed into the spoof fallback.
    assert "spoof" in exc.cause.lower()


def test_anti_spoof_models_url_value_error_raises_typed_error() -> None:
    """Even a stripped-down message that only carries the
    ``anti_spoof_models`` URL fragment (no chain emoji, no "downloading"
    verb) must be classified as model-load failure, not spoof verdict."""

    detector = _build_detector()
    minimal_message = (
        "Failed to fetch weights from "
        "https://example.invalid/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
    )

    def fake_extract_faces(image, anti_spoofing):  # noqa: ARG001
        raise ValueError(minimal_message)

    with patch.object(detector, "_extract_faces", side_effect=fake_extract_faces):
        with pytest.raises(LivenessModelLoadError):
            detector.detect_sync(_dummy_image())


def test_generic_value_error_propagates_unchanged() -> None:
    """A ValueError that matches none of the specific markers must
    propagate as today — no silent FaceNotDetectedError, no
    LivenessModelLoadError, no spoof-tagged fallback."""

    detector = _build_detector()

    def fake_extract_faces(image, anti_spoofing):  # noqa: ARG001
        raise ValueError("Something else went sideways in the detector backend")

    with patch.object(detector, "_extract_faces", side_effect=fake_extract_faces):
        with pytest.raises(ValueError) as exc_info:
            detector.detect_sync(_dummy_image())

    msg = str(exc_info.value)
    assert "Something else went sideways" in msg
    # Sanity: must not be coerced into the typed errors.
    assert not isinstance(exc_info.value, LivenessModelLoadError)
    assert not isinstance(exc_info.value, FaceNotDetectedError)


def test_no_face_value_error_routes_to_face_not_detected() -> None:
    """Sanity-pin the unchanged 'no face' route so a future refactor of
    the catch block doesn't silently regress this branch."""

    detector = _build_detector()

    def fake_extract_faces(image, anti_spoofing):  # noqa: ARG001
        raise ValueError("Face could not be detected in the image")

    with patch.object(detector, "_extract_faces", side_effect=fake_extract_faces):
        with pytest.raises(FaceNotDetectedError):
            detector.detect_sync(_dummy_image())


# ----------------------------------------------------------------------
# Pure-classifier tests — exercise the discriminator helpers directly.
# Cheap, deterministic, and document the marker set in one place.
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "msg",
    [
        "spoof detected in given image.",
        "Spoof detected in the given image.",
    ],
)
def test_is_spoof_verdict_matches_real_spoof_messages(msg: str) -> None:
    assert DeepFaceDetector._is_spoof_verdict(msg.lower()) is True


@pytest.mark.parametrize(
    "msg",
    [
        # The download failure mentions "spoof" via the URL but is not a verdict.
        "⛓️‍💥 An exception occurred while downloading 2.7_80x80_MiniFASNetV2.pth "
        "from https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/"
        "resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth. Consider downloading "
        "it manually to /root/.deepface/weights/2.7_80x80_MiniFASNetV2.pth.",
        # Bare 'spoof' substring (the historical false-positive case) must NOT
        # be classified as a spoof verdict.
        "Could not load anti_spoof_models weight file",
    ],
)
def test_is_spoof_verdict_does_not_match_non_verdict_messages(msg: str) -> None:
    assert DeepFaceDetector._is_spoof_verdict(msg.lower()) is False


def test_is_model_download_failure_matches_canonical_message() -> None:
    msg = (
        "⛓️‍💥 An exception occurred while downloading 2.7_80x80_MiniFASNetV2.pth "
        "from https://example.invalid/anti_spoof_models/x.pth. "
        "Consider downloading it manually to /root/.deepface/weights/x.pth."
    ).lower()
    assert DeepFaceDetector._is_model_download_failure(msg) is True


def test_is_model_download_failure_skips_pure_spoof_verdict() -> None:
    assert (
        DeepFaceDetector._is_model_download_failure("spoof detected in given image.")
        is False
    )
