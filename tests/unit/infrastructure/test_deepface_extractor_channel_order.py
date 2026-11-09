"""The server Facenet512 path must feed the model RGB.

Facenet512's weights (davidsandberg/facenet Inception ResNet v1, 2018, converted
to Keras by DeepFace) were trained on RGB images (``tf.image.decode_image``).
DeepFace 0.0.98 ``represent`` flips the RGB face from ``extract_faces`` to BGR
before the forward pass, so calling ``represent`` with a detector backend feeds
BGR. The extractor therefore detects and aligns with ``extract_faces`` (RGB
face) and hands that face to ``represent`` with ``detector_backend="skip"``,
which passes it to the model unchanged.

DeepFace is replaced by a recording double: the CI unit image has no
TensorFlow, and the property under test is which array reaches ``represent``.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import numpy as np
import pytest

from app.domain.embedding_pipeline import FACENET_CHANNEL_ORDER
from app.infrastructure.ml.extractors.deepface_extractor import DeepFaceExtractor


class _RecordingDeepFace:
    def __init__(self, face_rgb: np.ndarray) -> None:
        self.face_rgb = face_rgb
        self.extract_kwargs: dict[str, Any] = {}
        self.represent_kwargs: dict[str, Any] = {}

    def extract_faces(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.extract_kwargs = kwargs
        return [{"face": self.face_rgb, "facial_area": {}, "confidence": 0.99}]

    def represent(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.represent_kwargs = kwargs
        return [{"embedding": np.ones(512, dtype=np.float32).tolist()}]


@pytest.fixture
def red_face() -> np.ndarray:
    face = np.zeros((40, 30, 3), dtype=np.float64)
    face[..., 0] = 1.0  # pure red in RGB, values in [0, 1] as extract_faces returns
    return face


@pytest.fixture
def deepface_double(monkeypatch: pytest.MonkeyPatch, red_face: np.ndarray) -> _RecordingDeepFace:
    double = _RecordingDeepFace(red_face)
    module = types.ModuleType("deepface")
    module.DeepFace = double  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepface", module)
    return double


def _extractor() -> DeepFaceExtractor:
    extractor = DeepFaceExtractor.__new__(DeepFaceExtractor)
    extractor._model_name = "Facenet512"
    extractor._detector_backend = "mtcnn"
    extractor._enforce_detection = False
    return extractor


def test_extract_sync_WhenFaceIsRed_ShouldFeedTheModelRedInTheFirstChannel(
    deepface_double: _RecordingDeepFace,
) -> None:
    bgr_crop = np.zeros((60, 50, 3), dtype=np.uint8)

    _extractor().extract_sync(bgr_crop)

    fed = deepface_double.represent_kwargs["img_path"]
    assert deepface_double.represent_kwargs["detector_backend"] == "skip"
    np.testing.assert_array_equal(fed[..., 0], 1.0)
    np.testing.assert_array_equal(fed[..., 2], 0.0)


def test_extract_sync_WhenCalled_ShouldDetectAndAlignTheCropAsBefore(
    deepface_double: _RecordingDeepFace,
) -> None:
    bgr_crop = np.zeros((60, 50, 3), dtype=np.uint8)

    _extractor().extract_sync(bgr_crop)

    kwargs = deepface_double.extract_kwargs
    assert kwargs["img_path"] is bgr_crop
    assert kwargs["detector_backend"] == "mtcnn"
    assert kwargs["enforce_detection"] is False
    assert kwargs["align"] is True
    assert kwargs["color_face"] == "rgb"
    assert deepface_double.represent_kwargs["model_name"] == "Facenet512"
    assert deepface_double.represent_kwargs["normalization"] == "base"


def test_extract_sync_WhenCalled_ShouldReturnAnL2NormalizedVector(
    deepface_double: _RecordingDeepFace,
) -> None:
    vec = _extractor().extract_sync(np.zeros((60, 50, 3), dtype=np.uint8))

    assert vec.shape == (512,)
    assert np.linalg.norm(vec) == pytest.approx(1.0, abs=1e-6)


def test_FACENET_CHANNEL_ORDER_WhenRead_ShouldBeRgb() -> None:
    assert FACENET_CHANNEL_ORDER == "RGB"
