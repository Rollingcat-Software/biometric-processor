"""Unit tests for LiveCameraAnalysisUseCase.

P0 regression (INVESTIGATION_MASTER_2026-05-07, T0-4):
``LiveCameraAnalysisUseCase.analyze_frame`` previously returned
``is_live=True`` whenever ``self._liveness_detector`` was ``None`` (DI failure
at boot time, env-var typo, missing model file). That silently approved every
frame on ``/live-analysis/*``. This test pins the fail-CLOSED contract:
when no detector is wired, the use case must return ``is_live=False`` with
``metadata.reason == 'liveness_detector_unavailable'``.
"""

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app.api.schemas.live_analysis import AnalysisMode
from app.application.use_cases.live_camera_analysis import LiveCameraAnalysisUseCase


def _make_detection(bbox=(50, 50, 100, 100), confidence=0.95):
    """Build a duck-typed detection mock matching the attrs the use case reads.

    ``live_camera_analysis.py`` accesses ``detection.x/y/width/height`` and
    calls ``detection.get_face_region(image)`` — so the mock just exposes
    those attributes plus a callable ``get_face_region`` returning a slice
    of the input frame.
    """
    x, y, w, h = bbox
    detection = Mock()
    detection.x = x
    detection.y = y
    detection.width = w
    detection.height = h
    detection.confidence = confidence
    detection.landmarks = None
    detection.get_face_region = lambda image: image[y : y + h, x : x + w]
    return detection


@pytest.mark.asyncio
async def test_liveness_detector_none_returns_is_live_false_with_reason():
    """P0 fail-closed: missing liveness detector MUST NOT auto-approve frames.

    Constructs the use case with ``liveness_detector=None``, runs the LIVENESS
    analysis mode, and asserts:
    - ``response.liveness.is_live`` is False (was True pre-fix)
    - ``response.liveness.method`` is "unavailable"
    - ``response.liveness.metadata['reason']`` is "liveness_detector_unavailable"
    - ``response.liveness.confidence`` is 0.0 (no signal, so no confidence)
    """
    detector = Mock()
    detector.detect = AsyncMock(return_value=_make_detection())

    quality_assessor = Mock()
    quality = Mock()
    quality.score = 80.0
    quality.is_acceptable = True
    quality.get_issues = lambda: []
    quality.blur_score = 0.0
    quality.brightness_score = 0.0
    quality.sharpness_score = 0.0
    quality_assessor.assess = AsyncMock(return_value=quality)

    use_case = LiveCameraAnalysisUseCase(
        detector=detector,
        quality_assessor=quality_assessor,
        liveness_detector=None,  # the bug: DI failure
    )

    image = np.zeros((300, 300, 3), dtype=np.uint8)
    response = await use_case.analyze_frame(image, mode=AnalysisMode.LIVENESS)

    assert response.error is None or "Analysis error" not in response.error, (
        f"Unexpected analysis error: {response.error!r}"
    )
    assert response.liveness is not None, "liveness result must be populated"
    assert response.liveness.is_live is False, (
        "fail-closed contract violated: detector=None was approved as live"
    )
    assert response.liveness.method == "unavailable"
    assert response.liveness.confidence == 0.0
    assert (
        response.liveness.metadata.get("reason") == "liveness_detector_unavailable"
    ), (
        "missing-detector reason must be machine-parseable for ops/alerting; "
        f"got metadata={response.liveness.metadata!r}"
    )


@pytest.mark.asyncio
async def test_liveness_detector_none_fail_closed_in_full_analysis_mode():
    """FULL_ANALYSIS mode also runs liveness; same fail-closed contract applies."""
    detector = Mock()
    detector.detect = AsyncMock(return_value=_make_detection())

    quality_assessor = Mock()
    quality = Mock()
    quality.score = 80.0
    quality.is_acceptable = True
    quality.get_issues = lambda: []
    quality.blur_score = 0.0
    quality.brightness_score = 0.0
    quality.sharpness_score = 0.0
    quality_assessor.assess = AsyncMock(return_value=quality)

    use_case = LiveCameraAnalysisUseCase(
        detector=detector,
        quality_assessor=quality_assessor,
        liveness_detector=None,
    )

    image = np.zeros((300, 300, 3), dtype=np.uint8)
    response = await use_case.analyze_frame(image, mode=AnalysisMode.FULL_ANALYSIS)

    assert response.liveness is not None
    assert response.liveness.is_live is False
    assert (
        response.liveness.metadata.get("reason") == "liveness_detector_unavailable"
    )


@pytest.mark.asyncio
async def test_enrollment_ready_mode_blocks_when_detector_missing():
    """Defense-in-depth: ENROLLMENT_READY must NOT mark a frame ready when
    liveness cannot be evaluated. The enrollment-readiness recommendation
    string carries the user-facing failure reason.
    """
    detector = Mock()
    detector.detect = AsyncMock(return_value=_make_detection())

    quality_assessor = Mock()
    quality = Mock()
    quality.score = 95.0  # high quality so only liveness can block
    quality.is_acceptable = True
    quality.get_issues = lambda: []
    quality.blur_score = 0.0
    quality.brightness_score = 0.0
    quality.sharpness_score = 0.0
    quality_assessor.assess = AsyncMock(return_value=quality)

    use_case = LiveCameraAnalysisUseCase(
        detector=detector,
        quality_assessor=quality_assessor,
        liveness_detector=None,
    )

    image = np.zeros((300, 300, 3), dtype=np.uint8)
    response = await use_case.analyze_frame(
        image, mode=AnalysisMode.ENROLLMENT_READY
    )

    assert response.enrollment_ready is not None
    assert response.enrollment_ready.ready is False, (
        "enrollment must be blocked when the liveness detector is missing"
    )
    assert response.enrollment_ready.liveness_met is False
