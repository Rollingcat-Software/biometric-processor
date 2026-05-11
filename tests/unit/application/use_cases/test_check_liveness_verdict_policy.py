"""Regression tests pinning the liveness verdict policy.

T2-E (INVESTIGATION_MASTER_2026-05-07 P1, INVESTIGATION_FAILOPEN_2026-05-07.md):
``CheckLivenessUseCase`` must not silently fail-open when DeepFace flags a
spoof and the primary backend (e.g. UniFace) returns ``is_live=True`` with
high confidence. The 2026-05-08 fix introduced ``LIVENESS_VERDICT_POLICY`` —
verified on 2026-05-11 that:

* default policy is ``"conservative"``;
* under the conservative policy DeepFace ``spoof`` ALWAYS vetoes regardless
  of primary-backend confidence;
* the resulting payload sets ``deepface_veto_applied=True`` and
  ``verdict_contradiction=True``.

These tests pin the contract so a future "optimistic by default" regression
fails loud.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest

from app.application.use_cases import check_liveness as check_liveness_module
from app.application.use_cases.check_liveness import (
    DEEPFACE_VETO_CONFIDENCE_THRESHOLD,
    CheckLivenessUseCase,
)
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.liveness_result import LivenessResult


def _write_dummy_image(tmp_path: Path) -> str:
    img = np.full((200, 200, 3), 128, dtype=np.uint8)
    rng = np.random.default_rng(seed=1)
    noise = rng.integers(-40, 40, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), img)
    return str(path)


def _build_use_case(
    spoof_label: str = "spoof",
    spoof_score: float = 0.95,
    primary_is_live: bool = True,
    primary_confidence: float = 0.97,
) -> CheckLivenessUseCase:
    detection = FaceDetectionResult(
        found=True,
        bounding_box=(0, 0, 200, 200),
        landmarks=None,
        confidence=0.95,
        antispoof_score=spoof_score,
        antispoof_label=spoof_label,
    )
    detector = Mock()
    detector.detect = AsyncMock(return_value=detection)

    liveness_detector = Mock()
    liveness_detector.check_liveness = AsyncMock(
        return_value=LivenessResult(
            is_live=primary_is_live,
            score=primary_confidence * 100.0,
            challenge="passive",
            challenge_completed=True,
            confidence=primary_confidence,
            details={"texture": 0.8},
        )
    )
    return CheckLivenessUseCase(
        detector=detector,
        liveness_detector=liveness_detector,
        landmark_detector=None,
    )


def test_default_policy_is_conservative() -> None:
    """The shipped default must be the secure 'conservative' policy.

    We re-instantiate ``Settings`` from a clean env so a tester's local
    ``LIVENESS_VERDICT_POLICY=optimistic`` override can't false-pass this.
    """
    from app.core.config import Settings

    fresh = Settings(_env_file=None)  # type: ignore[call-arg]
    assert fresh.LIVENESS_VERDICT_POLICY == "conservative", (
        "Default verdict policy regressed — INVESTIGATION_FAILOPEN_2026-05-07 "
        "requires conservative-by-default to prevent fail-open."
    )


@pytest.fixture
def _force_anti_spoofing_enabled(monkeypatch):
    """Ensure the anti-spoofing branch runs regardless of host env."""
    monkeypatch.setattr(
        check_liveness_module.settings, "ANTI_SPOOFING_ENABLED", True, raising=True
    )
    monkeypatch.setattr(
        check_liveness_module.settings, "ANTI_SPOOFING_THRESHOLD", 0.5, raising=True
    )
    yield


@pytest.mark.asyncio
async def test_conservative_deepface_spoof_vetoes_high_confidence_uniface(
    tmp_path, monkeypatch, _force_anti_spoofing_enabled
) -> None:
    """Conservative policy: DeepFace 'spoof' wins even when UniFace says
    live with confidence well above the legacy 0.85 veto threshold."""
    monkeypatch.setattr(
        check_liveness_module.settings,
        "LIVENESS_VERDICT_POLICY",
        "conservative",
        raising=True,
    )
    path = _write_dummy_image(tmp_path)
    use_case = _build_use_case(
        spoof_label="spoof",
        spoof_score=0.95,
        primary_is_live=True,
        primary_confidence=0.97,  # >> DEEPFACE_VETO_CONFIDENCE_THRESHOLD (0.85)
    )
    assert 0.97 > DEEPFACE_VETO_CONFIDENCE_THRESHOLD

    with patch(
        "app.application.use_cases.check_liveness.extract_face_signal_metrics",
        return_value=Mock(to_dict=lambda: {}),
    ):
        result = await use_case.execute(path)

    # Veto must fire — final verdict spoof_suspected, contradiction logged.
    assert result.is_live is False, (
        "Conservative policy must veto: DeepFace=spoof + UniFace=live(0.97) "
        "should NOT pass."
    )
    assert result.details["deepface_veto_applied"] is True
    assert result.details["verdict_contradiction"] is True
    assert result.details["verdict_policy"] == "conservative"


@pytest.mark.asyncio
async def test_conservative_agreeing_live_passes_through(
    tmp_path, monkeypatch, _force_anti_spoofing_enabled
) -> None:
    """No contradiction -> no veto, no contradiction flag."""
    monkeypatch.setattr(
        check_liveness_module.settings,
        "LIVENESS_VERDICT_POLICY",
        "conservative",
        raising=True,
    )
    path = _write_dummy_image(tmp_path)
    use_case = _build_use_case(
        spoof_label="real",
        spoof_score=0.9,
        primary_is_live=True,
        primary_confidence=0.92,
    )

    with patch(
        "app.application.use_cases.check_liveness.extract_face_signal_metrics",
        return_value=Mock(to_dict=lambda: {}),
    ):
        result = await use_case.execute(path)

    assert result.is_live is True
    assert result.details["deepface_veto_applied"] is False
    assert result.details["verdict_contradiction"] is False


@pytest.mark.asyncio
async def test_optimistic_policy_only_vetoes_below_threshold(
    tmp_path, monkeypatch, _force_anti_spoofing_enabled
) -> None:
    """Sanity-check the legacy 'optimistic' path still honours the
    0.85 threshold and emits a contradiction warning when UniFace 'wins'."""
    monkeypatch.setattr(
        check_liveness_module.settings,
        "LIVENESS_VERDICT_POLICY",
        "optimistic",
        raising=True,
    )

    path = _write_dummy_image(tmp_path)
    use_case = _build_use_case(
        spoof_label="spoof",
        spoof_score=0.95,
        primary_is_live=True,
        primary_confidence=0.97,  # > 0.85 -> primary wins under optimistic
    )

    with patch(
        "app.application.use_cases.check_liveness.extract_face_signal_metrics",
        return_value=Mock(to_dict=lambda: {}),
    ):
        result = await use_case.execute(path)

    # Optimistic + high primary confidence: NO veto, but contradiction
    # MUST be flagged so the operator log catches the disagreement.
    assert result.is_live is True
    assert result.details["deepface_veto_applied"] is False
    assert result.details["verdict_contradiction"] is True
    assert result.details["verdict_policy"] == "optimistic"
