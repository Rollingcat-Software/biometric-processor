"""Integration tests for hybrid fusion with real collected data.

These tests validate hybrid fusion against labeled test frames collected
from `app/tools/test_data_collector.py`.

Run test data collector first:
    python app/tools/test_data_collector.py

Then run these tests:
    pytest tests/integration/test_hybrid_fusion_real_data.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import cv2
import pytest

from app.application.services.device_spoof_risk_evaluator import DeviceSpoofRiskEvaluator
from app.application.services.hybrid_fusion_evaluator import HybridFusionEvaluator
from app.application.use_cases.live_camera_analysis import LiveCameraAnalysisUseCase
from app.api.schemas.live_analysis import AnalysisMode
from app.core.config import get_settings
from app.infrastructure.ml.liveness.face_detector_factory import FaceDetectorFactory
from app.infrastructure.ml.liveness.liveness_detector_factory import LivenessDetectorFactory
from app.infrastructure.ml.liveness.quality_assessor_factory import QualityAssessorFactory
from app.infrastructure.ml.liveness.rppg_analyzer import RPPGAnalyzer


TEST_FRAMES_DIR = Path("data/test_frames")
SUMMARY_FILE = TEST_FRAMES_DIR / "summary.jsonl"


def load_test_frames() -> list[dict]:
    """Load collected test frame metadata."""
    if not SUMMARY_FILE.exists():
        pytest.skip(f"Test data not found. Run: python app/tools/test_data_collector.py")

    frames = []
    with open(SUMMARY_FILE) as f:
        for line in f:
            if line.strip():
                frames.append(json.loads(line))
    return frames


@pytest.fixture
async def use_case():
    """Create LiveCameraAnalysisUseCase with hybrid fusion enabled."""
    settings = get_settings()

    detector = FaceDetectorFactory.create(
        backend=settings.FACE_DETECTION_BACKEND,
        device=settings.MODEL_DEVICE,
    )
    liveness_detector = LivenessDetectorFactory.create(
        backend=settings.get_liveness_backend(),
        device=settings.MODEL_DEVICE,
    )
    quality_assessor = QualityAssessorFactory.create(
        device=settings.MODEL_DEVICE,
    )
    device_spoof_evaluator = DeviceSpoofRiskEvaluator()
    rppg_analyzer = RPPGAnalyzer()
    hybrid_fusion_evaluator = HybridFusionEvaluator(
        threshold=settings.LIVENESS_FUSION_THRESHOLD
    )

    return LiveCameraAnalysisUseCase(
        detector=detector,
        quality_assessor=quality_assessor,
        liveness_detector=liveness_detector,
        rppg_analyzer=rppg_analyzer,
        device_spoof_risk_evaluator=device_spoof_evaluator,
        settings=settings,
        hybrid_fusion_evaluator=hybrid_fusion_evaluator,
    )


@pytest.mark.asyncio
async def test_hybrid_fusion_accuracy_on_collected_live_frames(use_case):
    """Validate hybrid fusion on real LIVE frames."""
    frames = load_test_frames()
    live_frames = [f for f in frames if f["label"] == "live"]

    if not live_frames:
        pytest.skip("No LIVE frames collected")

    correct = 0
    total = len(live_frames)

    for frame_meta in live_frames:
        image_path = frame_meta["image_path"]
        frame = cv2.imread(image_path)
        if frame is None:
            continue

        response = await use_case.analyze_frame(
            image=frame, mode=AnalysisMode.LIVENESS
        )

        if response.liveness:
            # LIVE frames should be detected as live
            if response.liveness.is_live:
                correct += 1

    accuracy = correct / total if total > 0 else 0.0
    assert accuracy >= 0.80, f"LIVE accuracy {accuracy:.1%} < 80%"


@pytest.mark.asyncio
async def test_hybrid_fusion_accuracy_on_collected_spoof_frames(use_case):
    """Validate hybrid fusion on real SPOOF frames."""
    frames = load_test_frames()
    spoof_frames = [f for f in frames if f["label"] == "spoof"]

    if not spoof_frames:
        pytest.skip("No SPOOF frames collected")

    correct = 0
    total = len(spoof_frames)

    for frame_meta in spoof_frames:
        image_path = frame_meta["image_path"]
        frame = cv2.imread(image_path)
        if frame is None:
            continue

        response = await use_case.analyze_frame(
            image=frame, mode=AnalysisMode.LIVENESS
        )

        if response.liveness:
            # SPOOF frames should be detected as spoof
            if not response.liveness.is_live:
                correct += 1

    accuracy = correct / total if total > 0 else 0.0
    assert accuracy >= 0.80, f"SPOOF accuracy {accuracy:.1%} < 80%"


@pytest.mark.asyncio
async def test_hybrid_fusion_enabled_metadata(use_case):
    """Verify hybrid fusion metadata is present in response."""
    frames = load_test_frames()
    if not frames:
        pytest.skip("No frames collected")

    frame_path = frames[0]["image_path"]
    frame = cv2.imread(frame_path)
    if frame is None:
        pytest.skip("Cannot read frame image")

    response = await use_case.analyze_frame(
        image=frame, mode=AnalysisMode.LIVENESS
    )

    # Check metadata
    assert response.liveness is not None
    assert "hybrid_fusion_enabled" in response.liveness.checks
    assert "hybrid_fusion_is_spoof" in response.liveness.checks
    assert "hybrid_fusion_spoof_score" in response.liveness.scores
    assert "hybrid_fusion_reasoning" in response.liveness.metadata


def test_summary_report():
    """Generate accuracy report from collected frames."""
    if not SUMMARY_FILE.exists():
        pytest.skip("No summary file")

    frames = load_test_frames()
    if not frames:
        pytest.skip("No frames in summary")

    live_frames = [f for f in frames if f["label"] == "live"]
    spoof_frames = [f for f in frames if f["label"] == "spoof"]

    print("\n" + "=" * 70)
    print("HYBRID FUSION TEST DATA SUMMARY")
    print("=" * 70)
    print(f"\nTotal frames collected: {len(frames)}")
    print(f"  LIVE:  {len(live_frames)}")
    print(f"  SPOOF: {len(spoof_frames)}")
    print(f"\nTest data location: {TEST_FRAMES_DIR.absolute()}")
    print("=" * 70 + "\n")

    # Provide guidance
    print("📊 Next steps:")
    print("1. Review collected frames in data/test_frames/")
    print("2. Run accuracy tests:")
    print("   pytest tests/integration/test_hybrid_fusion_real_data.py -v")
    print("3. Check individual frame metrics:")
    print("   cat data/test_frames/summary.jsonl | jq '.'")
