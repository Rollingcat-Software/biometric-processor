"""Regression tests for the anti-spoof model-missing policy.

Background — 2026-05-12 compound liveness bug:
    When the DeepFace anti-spoof model (``MiniFASNetV2``) couldn't be
    downloaded on first inference, the detector silently fell into the
    spoof-fallback path and tagged every user as
    ``antispoof_label="spoof"``. The conservative verdict policy then
    rejected every user with ``is_live=False, score=99.47`` (UniFace's
    high confidence + DeepFace's "spoof" label).

    The fix introduces ``LivenessModelLoadError`` and a per-deployment
    policy ``LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY`` controlling how
    the use case responds when that error fires:

      * ``hard_error`` (default): re-raise so the operator sees a 5xx on
        the very first verify request instead of silently bricking auth.
      * ``fail_closed``: respond with ``is_live=False`` and reason
        ``"antispoof_model_missing"``.
      * ``fail_open``: respond with ``is_live=True`` and a WARNING log
        (use only when verify is a soft gate AND an external monitor
        catches the warning).

    These tests pin the contract of all three policies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest

from app.application.use_cases import check_liveness as check_liveness_module
from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.domain.exceptions.liveness_errors import LivenessModelLoadError


def _write_dummy_image(tmp_path: Path) -> str:
    img = np.full((200, 200, 3), 128, dtype=np.uint8)
    rng = np.random.default_rng(seed=2)
    noise = rng.integers(-40, 40, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), img)
    return str(path)


def _build_use_case_with_model_load_error() -> CheckLivenessUseCase:
    """Detector that always raises ``LivenessModelLoadError`` on detect."""
    detector = Mock()
    detector.detect = AsyncMock(
        side_effect=LivenessModelLoadError(
            model_name="MiniFASNetV2",
            cause=(
                "⛓️‍💥 An exception occurred while downloading "
                "2.7_80x80_MiniFASNetV2.pth from "
                "https://example.invalid/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth. "
                "Consider downloading it manually to /root/.deepface/weights/"
                "2.7_80x80_MiniFASNetV2.pth."
            ),
            target_path="/root/.deepface/weights/2.7_80x80_MiniFASNetV2.pth",
        )
    )
    liveness_detector = Mock()
    # Should never be called when detect raises.
    liveness_detector.check_liveness = AsyncMock(
        side_effect=AssertionError("check_liveness must not run when detect raises")
    )
    return CheckLivenessUseCase(
        detector=detector,
        liveness_detector=liveness_detector,
        landmark_detector=None,
    )


@pytest.mark.asyncio
async def test_hard_error_policy_propagates_liveness_model_load_error(
    tmp_path, monkeypatch
) -> None:
    """Default ``hard_error`` policy must re-raise so the operator sees
    a 5xx, instead of silently auto-failing every user."""

    monkeypatch.setattr(
        check_liveness_module.settings,
        "LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY",
        "hard_error",
        raising=True,
    )
    use_case = _build_use_case_with_model_load_error()
    path = _write_dummy_image(tmp_path)

    with pytest.raises(LivenessModelLoadError) as exc_info:
        await use_case.execute(path)

    assert "MiniFASNetV2" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fail_closed_policy_returns_is_live_false_with_reason(
    tmp_path, monkeypatch
) -> None:
    """``fail_closed`` policy: ``is_live=False`` with reason
    ``"antispoof_model_missing"`` and the operator-meaningful model
    details preserved in ``details``."""

    monkeypatch.setattr(
        check_liveness_module.settings,
        "LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY",
        "fail_closed",
        raising=True,
    )
    use_case = _build_use_case_with_model_load_error()
    path = _write_dummy_image(tmp_path)

    result = await use_case.execute(path)

    assert result.is_live is False
    assert result.score == 0.0
    assert result.details["reason"] == "antispoof_model_missing"
    assert result.details["antispoof_model_missing"] is True
    assert result.details["antispoof_model_name"] == "MiniFASNetV2"
    assert "2.7_80x80_MiniFASNetV2.pth" in result.details["antispoof_model_target_path"]
    assert result.details["antispoof_model_missing_policy"] == "fail_closed"


@pytest.mark.asyncio
async def test_fail_open_policy_accepts_but_emits_warning(
    tmp_path, monkeypatch, caplog
) -> None:
    """``fail_open`` policy: ``is_live=True`` but a WARNING is emitted
    so external monitoring can catch the operational issue."""

    monkeypatch.setattr(
        check_liveness_module.settings,
        "LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY",
        "fail_open",
        raising=True,
    )
    use_case = _build_use_case_with_model_load_error()
    path = _write_dummy_image(tmp_path)

    with caplog.at_level(logging.WARNING, logger="app.application.use_cases.check_liveness"):
        result = await use_case.execute(path)

    assert result.is_live is True
    assert result.details["reason"] == "antispoof_model_missing"
    assert result.details["antispoof_model_missing_policy"] == "fail_open"
    # The WARNING must include the model name + operator action hint.
    matching_warnings = [
        rec for rec in caplog.records
        if rec.levelno == logging.WARNING and "fail_open" in rec.getMessage()
    ]
    assert matching_warnings, (
        "fail_open must emit a WARNING log so external monitors can catch "
        "the missing anti-spoof model."
    )


@pytest.mark.asyncio
async def test_default_policy_is_hard_error(tmp_path) -> None:
    """The shipped default must be the loud ``hard_error`` policy.

    A fresh ``Settings`` instance — re-instantiated from a clean env so a
    tester's local override can't false-pass this — must report
    ``hard_error``.
    """
    from app.core.config import Settings

    fresh = Settings(_env_file=None)  # type: ignore[call-arg]
    assert fresh.LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY == "hard_error", (
        "Default model-missing policy regressed: the 2026-05-12 fix requires "
        "hard_error-by-default so operators see model-download failures "
        "loud instead of silently rejecting every user."
    )
