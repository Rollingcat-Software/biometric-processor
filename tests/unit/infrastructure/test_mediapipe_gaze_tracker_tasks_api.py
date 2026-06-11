"""Tests for MediaPipeGazeTracker after the mp.solutions → mp.tasks port.

Added 2026-05-12. The gaze tracker uses VIDEO running-mode, so we verify
both that ``detect_for_video`` is invoked (NOT ``detect``) and that the
monotonic timestamp counter only ever increases.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from app.infrastructure.ml.proctoring.mediapipe_gaze_tracker import (
    MediaPipeGazeTracker,
)


def _fake_face(num: int = 478):
    # Spread x/y in a way that triggers the iris/eye-corner math without
    # exercising degenerate divisions.
    return [
        SimpleNamespace(x=0.4 + (i % 17) * 0.005, y=0.5 + (i % 19) * 0.005, z=0.0)
        for i in range(num)
    ]


def _fake_result_with_face() -> SimpleNamespace:
    return SimpleNamespace(face_landmarks=[_fake_face()])


def _fake_empty_result() -> SimpleNamespace:
    return SimpleNamespace(face_landmarks=[])


class TestMediaPipeGazeTrackerTasksAPI:
    @pytest.mark.asyncio
    async def test_analyze_uses_detect_for_video_not_detect(self) -> None:
        tracker = MediaPipeGazeTracker()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect_for_video.return_value = _fake_result_with_face()

        with mock.patch(
            "app.infrastructure.ml.proctoring.mediapipe_gaze_tracker.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.proctoring.mediapipe_gaze_tracker.to_mp_image",
            side_effect=lambda x: x,
        ):
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            await tracker.analyze(image, session_id="s1")

        fake_landmarker.detect_for_video.assert_called_once()
        fake_landmarker.detect.assert_not_called()

    @pytest.mark.asyncio
    async def test_video_timestamps_strictly_monotonic(self) -> None:
        tracker = MediaPipeGazeTracker()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect_for_video.return_value = _fake_result_with_face()

        with mock.patch(
            "app.infrastructure.ml.proctoring.mediapipe_gaze_tracker.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.proctoring.mediapipe_gaze_tracker.to_mp_image",
            side_effect=lambda x: x,
        ):
            image = np.zeros((100, 100, 3), dtype=np.uint8)
            for _ in range(5):
                await tracker.analyze(image, session_id="s1")

        timestamps = [c.args[1] for c in fake_landmarker.detect_for_video.call_args_list]
        # The Tasks API rejects non-increasing timestamps with
        # InvalidArgumentError, so this invariant is a hard correctness
        # requirement.
        assert all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))

    @pytest.mark.asyncio
    async def test_no_face_returns_off_screen_result(self) -> None:
        tracker = MediaPipeGazeTracker()
        fake_landmarker = mock.MagicMock()
        fake_landmarker.detect_for_video.return_value = _fake_empty_result()

        with mock.patch(
            "app.infrastructure.ml.proctoring.mediapipe_gaze_tracker.create_face_landmarker",
            return_value=fake_landmarker,
        ), mock.patch(
            "app.infrastructure.ml.proctoring.mediapipe_gaze_tracker.to_mp_image",
            side_effect=lambda x: x,
        ):
            image = np.zeros((100, 100, 3), dtype=np.uint8)
            result = await tracker.analyze(image, session_id="s1")

        assert result.head_pose is None
        assert result.gaze_direction is None
        assert result.is_on_screen is False
        assert result.confidence == 0.0
