"""Unit tests for StubLivenessDetector."""

import pytest
import numpy as np

from app.infrastructure.ml.liveness.stub_liveness_detector import StubLivenessDetector
from app.domain.entities.liveness_result import LivenessResult


class TestStubLivenessDetector:
    """Test StubLivenessDetector."""

    def test_initialization_default_score(self):
        """Test initialization with default score."""
        detector = StubLivenessDetector()

        assert detector._default_score == 85.0
        assert detector.get_liveness_threshold() == 80.0
        assert detector.get_challenge_type() == "none"

    def test_initialization_custom_score(self):
        """Test initialization with custom default score."""
        detector = StubLivenessDetector(default_score=90.0)

        assert detector._default_score == 90.0

    @pytest.mark.asyncio
    async def test_check_liveness_returns_passing_result(self):
        """Test that check_liveness always returns passing result."""
        detector = StubLivenessDetector(default_score=85.0)

        # Create dummy image
        image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

        result = await detector.check_liveness(image)

        assert isinstance(result, LivenessResult)
        assert result.is_live is True
        assert result.liveness_score == 85.0
        assert result.challenge == "none"
        assert result.challenge_completed is True

    @pytest.mark.asyncio
    async def test_check_liveness_with_different_scores(self):
        """Test check_liveness with different default scores."""
        scores = [70.0, 80.0, 90.0, 95.0]

        for score in scores:
            detector = StubLivenessDetector(default_score=score)
            image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await detector.check_liveness(image)

            assert result.liveness_score == score
            assert result.is_live is True

    @pytest.mark.asyncio
    async def test_check_liveness_ignores_image_content(self):
        """Test that stub detector ignores actual image content."""
        detector = StubLivenessDetector(default_score=85.0)

        # Try with different images
        blank_image = np.zeros((100, 100, 3), dtype=np.uint8)
        noise_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        white_image = np.ones((150, 150, 3), dtype=np.uint8) * 255

        result1 = await detector.check_liveness(blank_image)
        result2 = await detector.check_liveness(noise_image)
        result3 = await detector.check_liveness(white_image)

        # All should return same result
        assert result1.liveness_score == result2.liveness_score == result3.liveness_score
        assert result1.is_live == result2.is_live == result3.is_live

    def test_get_challenge_type(self):
        """Test getting challenge type."""
        detector = StubLivenessDetector()

        assert detector.get_challenge_type() == "none"

    def test_get_liveness_threshold(self):
        """Test getting liveness threshold."""
        detector = StubLivenessDetector()

        assert detector.get_liveness_threshold() == 80.0

    @pytest.mark.asyncio
    async def test_result_structure(self):
        """Test that result has correct structure."""
        detector = StubLivenessDetector(default_score=92.0)
        image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

        result = await detector.check_liveness(image)

        # Check all required fields
        assert hasattr(result, 'is_live')
        assert hasattr(result, 'liveness_score')
        assert hasattr(result, 'challenge')
        assert hasattr(result, 'challenge_completed')

        # Check types
        assert isinstance(result.is_live, bool)
        assert isinstance(result.liveness_score, float)
        assert isinstance(result.challenge, str)
        assert isinstance(result.challenge_completed, bool)
