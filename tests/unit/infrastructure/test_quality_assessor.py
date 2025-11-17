"""Unit tests for QualityAssessor."""

import pytest
import numpy as np
import cv2

from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
from app.domain.entities.quality_assessment import QualityAssessment


class TestQualityAssessor:
    """Test QualityAssessor."""

    def test_initialization_default_thresholds(self):
        """Test initialization with default thresholds."""
        assessor = QualityAssessor()

        assert assessor._blur_threshold == 100.0
        assert assessor._min_face_size == 80
        assert assessor._quality_threshold == 70.0
        assert assessor.get_minimum_acceptable_score() == 70.0

    def test_initialization_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        assessor = QualityAssessor(
            blur_threshold=150.0,
            min_face_size=100,
            quality_threshold=80.0
        )

        assert assessor._blur_threshold == 150.0
        assert assessor._min_face_size == 100
        assert assessor._quality_threshold == 80.0

    @pytest.mark.asyncio
    async def test_assess_good_quality_image(self):
        """Test assessment of good quality image."""
        assessor = QualityAssessor()

        # Create sharp, well-lit image
        image = self._create_test_image(size=150, blur=False, brightness=128)

        result = await assessor.assess(image)

        assert isinstance(result, QualityAssessment)
        assert result.score > 0
        assert result.blur_score > 0
        assert result.lighting_score > 0
        assert result.face_size == 150

    @pytest.mark.asyncio
    async def test_assess_blurry_image(self):
        """Test assessment detects blurry images."""
        assessor = QualityAssessor(blur_threshold=100.0)

        # Create blurred image
        sharp_image = self._create_test_image(size=150, blur=False, brightness=128)
        blurry_image = cv2.GaussianBlur(sharp_image, (25, 25), 10)

        result = await assessor.assess(blurry_image)

        # Blurry image should have lower blur score
        assert result.blur_score < 100.0

    @pytest.mark.asyncio
    async def test_assess_dark_image(self):
        """Test assessment detects dark images."""
        assessor = QualityAssessor()

        # Create dark image
        dark_image = self._create_test_image(size=150, blur=False, brightness=30)

        result = await assessor.assess(dark_image)

        # Dark image should have low lighting score
        assert result.lighting_score < 50.0

    @pytest.mark.asyncio
    async def test_assess_bright_image(self):
        """Test assessment detects very bright images."""
        assessor = QualityAssessor()

        # Create very bright image
        bright_image = self._create_test_image(size=150, blur=False, brightness=250)

        result = await assessor.assess(bright_image)

        # Very bright image should have high lighting score
        assert result.lighting_score > 200.0

    @pytest.mark.asyncio
    async def test_assess_small_face(self):
        """Test assessment detects small faces."""
        assessor = QualityAssessor(min_face_size=80)

        # Create small face image
        small_image = self._create_test_image(size=50, blur=False, brightness=128)

        result = await assessor.assess(small_image)

        assert result.face_size == 50
        assert result.face_size < assessor._min_face_size

    @pytest.mark.asyncio
    async def test_assess_grayscale_image(self):
        """Test assessment works with grayscale images."""
        assessor = QualityAssessor()

        # Create grayscale image
        gray_image = np.random.randint(100, 150, (150, 150), dtype=np.uint8)

        result = await assessor.assess(gray_image)

        assert result.score > 0
        assert result.face_size == 150

    @pytest.mark.asyncio
    async def test_assess_color_image(self):
        """Test assessment works with color images."""
        assessor = QualityAssessor()

        # Create color image
        color_image = self._create_test_image(size=150, blur=False, brightness=128)

        result = await assessor.assess(color_image)

        assert result.score > 0
        assert result.face_size == 150

    @pytest.mark.asyncio
    async def test_acceptable_quality(self):
        """Test that good quality image is marked as acceptable."""
        assessor = QualityAssessor(
            blur_threshold=50.0,  # Lowered for test image
            min_face_size=80,
            quality_threshold=50.0  # Lowered for test
        )

        # Create good quality image
        image = self._create_test_image(size=150, blur=False, brightness=128)

        result = await assessor.assess(image)

        # Should be acceptable
        assert result.is_acceptable is True

    @pytest.mark.asyncio
    async def test_unacceptable_quality_blur(self):
        """Test that blurry image is marked as unacceptable."""
        assessor = QualityAssessor(blur_threshold=200.0)  # High threshold

        # Create blurred image
        sharp_image = self._create_test_image(size=150, blur=False, brightness=128)
        blurry_image = cv2.GaussianBlur(sharp_image, (31, 31), 15)

        result = await assessor.assess(blurry_image)

        # Should be unacceptable due to blur
        assert result.is_acceptable is False

    @pytest.mark.asyncio
    async def test_unacceptable_quality_size(self):
        """Test that small face is marked as unacceptable."""
        assessor = QualityAssessor(min_face_size=100)

        # Create small image
        small_image = self._create_test_image(size=60, blur=False, brightness=128)

        result = await assessor.assess(small_image)

        # Should be unacceptable due to size
        assert result.is_acceptable is False

    def test_detect_blur_sharp_image(self):
        """Test blur detection on sharp image."""
        # Create sharp pattern (checkerboard)
        image = np.zeros((100, 100), dtype=np.uint8)
        image[::2, ::2] = 255
        image[1::2, 1::2] = 255

        blur_score = QualityAssessor._detect_blur(image)

        # Sharp checkerboard should have high blur score
        assert blur_score > 100.0

    def test_detect_blur_blurry_image(self):
        """Test blur detection on blurry image."""
        # Create sharp pattern then blur it
        image = np.zeros((100, 100), dtype=np.uint8)
        image[::2, ::2] = 255
        image[1::2, 1::2] = 255

        blurry = cv2.GaussianBlur(image, (25, 25), 10)

        blur_score = QualityAssessor._detect_blur(blurry)

        # Blurry image should have lower score
        assert blur_score < 100.0

    def test_assess_lighting_dark(self):
        """Test lighting assessment on dark image."""
        dark_image = np.ones((100, 100), dtype=np.uint8) * 30

        lighting_score = QualityAssessor._assess_lighting(dark_image)

        assert lighting_score < 50.0

    def test_assess_lighting_bright(self):
        """Test lighting assessment on bright image."""
        bright_image = np.ones((100, 100), dtype=np.uint8) * 220

        lighting_score = QualityAssessor._assess_lighting(bright_image)

        assert lighting_score > 200.0

    def test_assess_lighting_good(self):
        """Test lighting assessment on well-lit image."""
        good_image = np.ones((100, 100), dtype=np.uint8) * 130

        lighting_score = QualityAssessor._assess_lighting(good_image)

        assert 50.0 < lighting_score < 200.0

    def test_normalize_blur_score_low(self):
        """Test blur score normalization for low values."""
        score = QualityAssessor._normalize_blur_score(50.0)

        # 50 out of 100 => 25 out of 100
        assert 20.0 < score < 30.0

    def test_normalize_blur_score_threshold(self):
        """Test blur score normalization at threshold."""
        score = QualityAssessor._normalize_blur_score(100.0)

        assert score == 50.0

    def test_normalize_blur_score_high(self):
        """Test blur score normalization for high values."""
        score = QualityAssessor._normalize_blur_score(300.0)

        # 300 maps to 50 + ((300-100)/400)*50 = 75
        assert 70.0 < score < 80.0

    def test_normalize_blur_score_very_high(self):
        """Test blur score normalization caps at 500."""
        score1 = QualityAssessor._normalize_blur_score(500.0)
        score2 = QualityAssessor._normalize_blur_score(1000.0)

        # Both should map to 100 (capped)
        assert score1 == 100.0
        assert score2 == 100.0

    def test_normalize_lighting_score_too_dark(self):
        """Test lighting normalization for dark images."""
        score = QualityAssessor._normalize_lighting_score(30.0)

        # 30 out of 50 => 30 out of 100
        assert 25.0 < score < 35.0

    def test_normalize_lighting_score_ideal(self):
        """Test lighting normalization for ideal brightness."""
        score = QualityAssessor._normalize_lighting_score(130.0)

        # Peak at 130, should be close to 100
        assert score > 95.0

    def test_normalize_lighting_score_too_bright(self):
        """Test lighting normalization for too bright images."""
        score = QualityAssessor._normalize_lighting_score(250.0)

        # Very bright, should be penalized
        assert score < 60.0

    def test_normalize_size_score_very_small(self):
        """Test size normalization for very small faces."""
        score = QualityAssessor._normalize_size_score(30)

        # 30 out of 50 => 15 out of 100
        assert 10.0 < score < 20.0

    def test_normalize_size_score_small(self):
        """Test size normalization for small faces."""
        score = QualityAssessor._normalize_size_score(65)

        # Between 50-80, mapped to 25-50 range
        assert 30.0 < score < 45.0

    def test_normalize_size_score_good(self):
        """Test size normalization for good-sized faces."""
        score = QualityAssessor._normalize_size_score(115)

        # Between 80-150, mapped to 50-100 range
        assert 70.0 < score < 85.0

    def test_normalize_size_score_large(self):
        """Test size normalization for large faces."""
        score = QualityAssessor._normalize_size_score(200)

        # Above 150, should be 100
        assert score == 100.0

    @staticmethod
    def _create_test_image(size: int, blur: bool, brightness: int) -> np.ndarray:
        """Create test image for quality assessment.

        Args:
            size: Image size (square)
            blur: Whether to blur the image
            brightness: Mean brightness level (0-255)

        Returns:
            Test image as numpy array
        """
        # Create image with specified brightness
        image = np.ones((size, size, 3), dtype=np.uint8) * brightness

        # Add some texture/pattern so blur detection works
        for i in range(0, size, 10):
            image[i:i+5, :] = min(255, brightness + 20)

        if blur:
            image = cv2.GaussianBlur(image, (15, 15), 5)

        return image
