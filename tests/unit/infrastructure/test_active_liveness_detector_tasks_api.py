"""Tests for ActiveLivenessDetector after the mp.solutions → mp.tasks port.

Added 2026-05-12. Verifies the detector adapts to the new
``result.face_landmarks[0][i].x`` shape and still returns a coherent
LivenessResult.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from app.domain.entities.liveness_result import LivenessResult
from app.infrastructure.ml.liveness.active_liveness_detector import (
    ActiveLivenessDetector,
)


def _fake_face(num: int = 478) -> list:
    return [
        SimpleNamespace(x=0.5 + (i % 7) * 0.01, y=0.5 + (i % 13) * 0.01, z=0.0)
        for i in range(num)
    ]


def _fake_result_with_face() -> SimpleNamespace:
    return SimpleNamespace(face_landmarks=[_fake_face()])


def _fake_empty_result() -> SimpleNamespace:
    return SimpleNamespace(face_landmarks=[])


class TestActiveLivenessDetectorTasksAPI:
    @pytest.mark.asyncio
    async def test_detect_returns_not_live_when_no_face(self) -> None:
        detector = ActiveLivenessDetector()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect.return_value = _fake_empty_result()

        with mock.patch(
            "app.infrastructure.ml.liveness.active_liveness_detector.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.liveness.active_liveness_detector.to_mp_image",
            side_effect=lambda x: x,
        ):
            result = await detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

        assert isinstance(result, LivenessResult)
        assert result.is_live is False
        assert result.liveness_score == 0.0
        assert result.details["eyes_open"] is False
        assert result.details["smiling"] is False

    @pytest.mark.asyncio
    async def test_detect_calls_landmarker_with_mp_image(self) -> None:
        detector = ActiveLivenessDetector()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect.return_value = _fake_result_with_face()

        sentinel_mp_image = object()
        with mock.patch(
            "app.infrastructure.ml.liveness.active_liveness_detector.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.liveness.active_liveness_detector.to_mp_image",
            return_value=sentinel_mp_image,
        ):
            await detector.detect(np.zeros((50, 50, 3), dtype=np.uint8))

        fake_landmarker.detect.assert_called_once_with(sentinel_mp_image)

    @pytest.mark.asyncio
    async def test_detect_propagates_runtime_error_when_landmarker_unavailable(self) -> None:
        detector = ActiveLivenessDetector()
        with mock.patch(
            "app.infrastructure.ml.liveness.active_liveness_detector.create_face_landmarker",
            return_value=None,
        ):
            with pytest.raises(RuntimeError):
                await detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))
