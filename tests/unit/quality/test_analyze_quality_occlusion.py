"""End-to-end occlusion integration test for ``AnalyzeQualityUseCase``.

Covers the new code path that replaced the hardcoded ``occlusion=0.0``:
the use case now invokes the region-based occlusion detector, surfaces a
structured ``occlusion_details`` payload on ``QualityMetrics``, and fails
the gate when a critical region (eyes) is occluded.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app.application.use_cases.analyze_quality import AnalyzeQualityUseCase
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_feedback import QualityFeedback


def _detection_for_full_image(size: int) -> FaceDetectionResult:
    """Build a detection result whose bounding box covers the whole image."""
    return FaceDetectionResult(
        found=True,
        bounding_box=(0, 0, size, size),
        landmarks=None,
        confidence=0.99,
    )


def _high_variance_rgb_face(size: int = 200) -> np.ndarray:
    """RGB face with enough texture to pass blur + occlusion gates."""
    rng = np.random.default_rng(seed=7)
    # Mid-grey base + heavy noise = high Laplacian variance.
    img = np.full((size, size, 3), 128, dtype=np.uint8)
    noise = rng.integers(-60, 60, size=(size, size, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


def _eye_occluded_rgb_face(size: int = 200) -> np.ndarray:
    """RGB face with both eye regions blacked out (sunglasses)."""
    img = _high_variance_rgb_face(size)
    # Cover both eye regions (matches REGION_SPECS).
    y0 = int(0.18 * size)
    y1 = int(0.45 * size)
    img[y0:y1, :] = 0
    return img


class TestAnalyzeQualityOcclusion:
    @pytest.mark.asyncio
    async def test_clean_face_passes_with_occlusion_details(self) -> None:
        image = _high_variance_rgb_face()
        detector = Mock()
        detector.detect = AsyncMock(return_value=_detection_for_full_image(200))
        quality_assessor = Mock()

        use_case = AnalyzeQualityUseCase(
            detector=detector, quality_assessor=quality_assessor
        )
        result = await use_case.execute(image=image)

        assert isinstance(result, QualityFeedback)
        # New contract: occlusion_details is always populated when a bbox
        # is present.
        assert result.metrics.occlusion_details is not None
        details = result.metrics.occlusion_details
        assert set(details.keys()) == {"score", "regions", "reason", "details"}
        # Clean noise should not flag eyes as critical.
        assert "left_eye" not in details["regions"]
        assert "right_eye" not in details["regions"]

    @pytest.mark.asyncio
    async def test_eye_occlusion_emits_high_severity_issue(self) -> None:
        image = _eye_occluded_rgb_face()
        detector = Mock()
        detector.detect = AsyncMock(return_value=_detection_for_full_image(200))
        quality_assessor = Mock()

        use_case = AnalyzeQualityUseCase(
            detector=detector, quality_assessor=quality_assessor
        )
        result = await use_case.execute(image=image)

        # Critical region flagged -> high-severity OCCLUSION issue -> fail.
        occlusion_issues = [i for i in result.issues if i.code == "OCCLUSION"]
        assert len(occlusion_issues) == 1, [i.code for i in result.issues]
        assert occlusion_issues[0].severity == "high"
        # Must not silently pass — the gate fails when a high-severity
        # issue is present.
        assert result.passed is False
        # Structured payload surfaces the offending region.
        details = result.metrics.occlusion_details
        assert details is not None
        assert any(r in details["regions"] for r in ("left_eye", "right_eye"))

    @pytest.mark.asyncio
    async def test_response_serialization_carries_occlusion_details(
        self,
    ) -> None:
        from app.domain.entities.quality_feedback import QualityFeedbackResponse

        image = _high_variance_rgb_face()
        detector = Mock()
        detector.detect = AsyncMock(return_value=_detection_for_full_image(200))
        quality_assessor = Mock()
        use_case = AnalyzeQualityUseCase(
            detector=detector, quality_assessor=quality_assessor
        )
        result = await use_case.execute(image=image)

        response = QualityFeedbackResponse.from_result(result)
        # The pydantic response model must preserve the new field for the
        # API contract; otherwise downstream clients can't surface region.
        assert response.metrics.occlusion_details is not None
        assert "score" in response.metrics.occlusion_details
