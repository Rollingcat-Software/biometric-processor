"""Tests for MediaPipeLandmarkDetector after the mp.solutions → mp.tasks port.

Added 2026-05-12. Real Tasks-API model loading requires the
`face_landmarker.task` asset on disk, which is not present in CI. These
tests therefore mock ``create_face_landmarker`` and assert the consumer
correctly adapts the new result shape (``result.face_landmarks[0][i].x``)
into the existing ``LandmarkResult`` domain entity.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from app.domain.exceptions.feature_errors import LandmarkError
from app.infrastructure.ml.landmarks.mediapipe_landmarks import (
    MediaPipeLandmarkDetector,
)


def _make_fake_landmark(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
    """Stand-in for mediapipe.tasks.python.components.containers.NormalizedLandmark."""
    return SimpleNamespace(x=x, y=y, z=z)


def _make_fake_result(num_landmarks: int = 468) -> SimpleNamespace:
    """Stand-in for mediapipe.tasks.python.vision.FaceLandmarkerResult.

    Tasks-API shape: ``result.face_landmarks`` is a list-of-lists where each
    inner list is a flat sequence of NormalizedLandmark objects (no ``.landmark``
    accessor unlike the legacy Solutions API).
    """
    face = [_make_fake_landmark(0.1 + i * 0.001, 0.2 + i * 0.001) for i in range(num_landmarks)]
    return SimpleNamespace(face_landmarks=[face])


class TestMediaPipeLandmarkDetectorTasksAPI:
    def test_returns_landmarks_when_face_present(self) -> None:
        detector = MediaPipeLandmarkDetector()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect.return_value = _make_fake_result(num_landmarks=468)

        with mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.to_mp_image",
            side_effect=lambda x: x,  # no-op
        ):
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            result = detector.detect(image)

        assert result.landmark_count == 468
        assert len(result.landmarks) == 468
        # First landmark uses x=0.1, y=0.2 (see _make_fake_landmark). The
        # detector multiplies normalised coords by image dims and casts to int.
        assert result.landmarks[0].x == int(0.1 * 640)
        assert result.landmarks[0].y == int(0.2 * 480)
        # 3D coordinate is dropped when include_3d=False (default).
        assert result.landmarks[0].z is None

    def test_include_3d_propagates_z(self) -> None:
        detector = MediaPipeLandmarkDetector()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect.return_value = _make_fake_result(num_landmarks=10)

        with mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.to_mp_image",
            side_effect=lambda x: x,
        ):
            image = np.zeros((100, 100, 3), dtype=np.uint8)
            result = detector.detect(image, include_3d=True)

        assert result.landmarks[5].z is not None

    def test_raises_landmark_error_when_no_face_detected(self) -> None:
        detector = MediaPipeLandmarkDetector()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect.return_value = SimpleNamespace(face_landmarks=[])

        with mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.to_mp_image",
            side_effect=lambda x: x,
        ):
            with pytest.raises(LandmarkError):
                detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))

    def test_raises_when_loader_returns_none(self) -> None:
        """If model asset is missing the loader returns None — caller must surface a clear error."""
        detector = MediaPipeLandmarkDetector()

        with mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.create_face_landmarker",
            return_value=None,
        ):
            with pytest.raises(LandmarkError):
                detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))

    def test_landmarker_is_cached_across_calls(self) -> None:
        detector = MediaPipeLandmarkDetector()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect.return_value = _make_fake_result()

        with mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.create_face_landmarker",
            return_value=fake_landmarker,
        ) as create_mock, mock.patch(
            "app.infrastructure.ml.landmarks.mediapipe_landmarks.to_mp_image",
            side_effect=lambda x: x,
        ):
            image = np.zeros((100, 100, 3), dtype=np.uint8)
            detector.detect(image)
            detector.detect(image)
            detector.detect(image)

        # Lazy init: create_face_landmarker should only run once.
        assert create_mock.call_count == 1
