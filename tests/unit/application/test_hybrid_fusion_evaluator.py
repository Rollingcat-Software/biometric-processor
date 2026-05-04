"""Unit tests for hybrid liveness fusion."""

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app.api.schemas.live_analysis import AnalysisMode
from app.application.services.hybrid_fusion_evaluator import HybridFusionEvaluator
from app.application.use_cases.live_camera_analysis import LiveCameraAnalysisUseCase
from app.core.config import Settings
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.liveness_result import LivenessResult as DomainLivenessResult


def test_hybrid_fusion_evaluator_detects_clear_spoof_case() -> None:
    evaluator = HybridFusionEvaluator()

    result = evaluator.evaluate(
        pretrained_spoof_score=0.95,
        custom_signals={
            "flash_response_score": 0.0,
            "flash_response_samples": 2,
            "rppg_live_signal": False,
            "rppg_available": True,
            "moire_score": 0.9,
            "device_replay_score": 0.8,
        },
    )

    assert result.is_spoof is True
    assert result.spoof_score > 0.8
    assert "SPOOF detected" in result.reasoning


def test_hybrid_fusion_evaluator_detects_clear_live_case() -> None:
    evaluator = HybridFusionEvaluator()

    result = evaluator.evaluate(
        pretrained_spoof_score=0.05,
        custom_signals={
            "flash_response_score": 0.95,
            "flash_response_samples": 2,
            "rppg_live_signal": True,
            "rppg_available": True,
            "moire_score": 0.1,
            "device_replay_score": 0.15,
        },
    )

    assert result.is_spoof is False
    assert result.spoof_score < 0.3
    assert "LIVE verified" in result.reasoning


@pytest.mark.asyncio
async def test_live_camera_analysis_applies_hybrid_fusion_when_enabled() -> None:
    image = np.full((120, 120, 3), 120, dtype=np.uint8)

    detector = Mock()
    detector.detect = AsyncMock(
        return_value=FaceDetectionResult(
            found=True,
            bounding_box=(10, 10, 80, 80),
            landmarks=None,
            confidence=0.97,
        )
    )
    quality_assessor = Mock()
    liveness_detector = Mock()
    liveness_detector.check_liveness = AsyncMock(
        return_value=DomainLivenessResult(
            is_live=True,
            score=92.0,
            challenge="uniface_minifasnet",
            challenge_completed=True,
            confidence=0.92,
            details={"backend_score": 0.92},
        )
    )
    liveness_detector.get_liveness_threshold = Mock(return_value=70.0)

    hybrid_fusion_evaluator = Mock()
    hybrid_fusion_evaluator.evaluate.return_value = Mock(
        is_spoof=True,
        confidence=0.82,
        spoof_score=0.84,
        breakdown={"pretrained": 0.08, "flash": 1.0, "rppg": 1.0, "moire": 0.9, "device": 0.85},
        reasoning="SPOOF detected (score=0.84). Primary indicator: flash (1.00)",
    )

    device_spoof_risk_evaluator = Mock()
    device_spoof_risk_evaluator.evaluate.return_value = Mock(
        to_dict=Mock(
            return_value={
                "moire_risk": 0.9,
                "flash_response_score": 0.0,
                "device_replay_risk": 0.85,
            }
        ),
        details={
            "flash_response_sample_count": 2.0,
            "reflection_compact_highlight_score": 0.6,
        },
    )

    settings = Settings(
        _env_file=None,
        JWT_ENABLED=False,
        LIVENESS_FUSION_ENABLED=True,
    )
    use_case = LiveCameraAnalysisUseCase(
        detector=detector,
        quality_assessor=quality_assessor,
        liveness_detector=liveness_detector,
        settings=settings,
        device_spoof_risk_evaluator=device_spoof_risk_evaluator,
        hybrid_fusion_evaluator=hybrid_fusion_evaluator,
    )

    response = await use_case.analyze_frame(image=image, mode=AnalysisMode.LIVENESS)

    assert response.liveness is not None
    assert response.liveness.is_live is False
    assert response.liveness.confidence == pytest.approx(0.82)
    assert response.liveness.scores["hybrid_fusion_spoof_score"] == pytest.approx(84.0)
    assert response.liveness.scores["liveness_score"] == pytest.approx(16.0)
    assert response.liveness.checks["hybrid_fusion_enabled"] is True
    assert response.liveness.checks["hybrid_fusion_is_spoof"] is True
    assert "SPOOF detected" in response.liveness.metadata["hybrid_fusion_reasoning"]
