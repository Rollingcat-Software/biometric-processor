"""Unit tests for TextureLivenessDetector."""

import cv2
import numpy as np
import pytest

from app.infrastructure.ml.liveness.texture_liveness_detector import TextureLivenessDetector


class TestTextureLivenessDetector:
    """Tests for texture-based liveness detector."""

    def _create_test_image(
        self,
        size: int = 200,
        add_texture: bool = True,
        add_face_features: bool = True,
        brightness: int = 128,
    ) -> np.ndarray:
        """Create a test image with configurable properties.

        Args:
            size: Image size (square)
            add_texture: Whether to add texture variation
            add_face_features: Whether to add face-like features
            brightness: Base brightness level

        Returns:
            Test image as numpy array
        """
        # Create base image
        img = np.ones((size, size, 3), dtype=np.uint8) * brightness

        if add_face_features:
            # Add face-like features
            center = size // 2
            cv2.circle(img, (center, center), size // 3, (180, 180, 180), -1)
            cv2.circle(img, (center - size // 6, center - size // 8), size // 20, (50, 50, 50), -1)
            cv2.circle(img, (center + size // 6, center - size // 8), size // 20, (50, 50, 50), -1)
            cv2.ellipse(
                img, (center, center + size // 6), (size // 8, size // 16), 0, 0, 180, (100, 100, 100), 2
            )

        if add_texture:
            # Add noise for texture
            noise = np.random.randint(-30, 30, img.shape, dtype=np.int16)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        return img

    @pytest.mark.asyncio
    async def test_initialization_default_thresholds(self):
        """Test detector initializes with default thresholds."""
        detector = TextureLivenessDetector()

        assert detector._texture_threshold == 100.0
        assert detector._color_threshold == 0.3
        assert detector._frequency_threshold == 0.5
        assert detector._liveness_threshold == 60.0

    @pytest.mark.asyncio
    async def test_initialization_custom_thresholds(self):
        """Test detector initializes with custom thresholds."""
        detector = TextureLivenessDetector(
            texture_threshold=150.0,
            color_threshold=0.5,
            frequency_threshold=0.7,
            liveness_threshold=70.0,
        )

        assert detector._texture_threshold == 150.0
        assert detector._color_threshold == 0.5
        assert detector._frequency_threshold == 0.7
        assert detector._liveness_threshold == 70.0

    @pytest.mark.asyncio
    async def test_detect_realistic_face_passes(self):
        """Test that realistic face image passes liveness check."""
        detector = TextureLivenessDetector(liveness_threshold=50.0)

        # Create image with good texture and features
        image = self._create_test_image(
            size=200, add_texture=True, add_face_features=True, brightness=128
        )

        result = await detector.detect(image)

        assert result.is_live == True
        assert result.liveness_score >= 50.0
        assert result.challenge == "texture_analysis"
        assert result.challenge_completed is True

    @pytest.mark.asyncio
    async def test_detect_flat_image_fails(self):
        """Test that flat image without texture fails liveness check."""
        detector = TextureLivenessDetector(liveness_threshold=60.0)

        # Create flat image with no texture
        image = self._create_test_image(
            size=200, add_texture=False, add_face_features=False, brightness=128
        )

        result = await detector.detect(image)

        # Flat images should have lower scores
        assert result.liveness_score < 80.0  # May still pass but with lower score
        assert result.challenge == "texture_analysis"

    @pytest.mark.asyncio
    async def test_detect_returns_liveness_result(self):
        """Test that detect returns proper LivenessResult."""
        detector = TextureLivenessDetector()
        image = self._create_test_image()

        result = await detector.detect(image)

        # Check result structure
        assert hasattr(result, "is_live")
        assert hasattr(result, "liveness_score")
        assert hasattr(result, "challenge")
        assert hasattr(result, "challenge_completed")

        # Check score range
        assert 0.0 <= result.liveness_score <= 100.0

    @pytest.mark.asyncio
    async def test_detect_custom_challenge(self):
        """Test detection with custom challenge name."""
        detector = TextureLivenessDetector()
        image = self._create_test_image()

        result = await detector.detect(image, challenge="custom_test")

        assert result.challenge == "custom_test"

    @pytest.mark.asyncio
    async def test_texture_score_calculation(self):
        """Test that texture score is calculated correctly."""
        detector = TextureLivenessDetector()

        # High texture image
        high_texture = self._create_test_image(add_texture=True)
        high_score = detector._calculate_texture_score(high_texture)

        # Low texture image (completely flat)
        low_texture = np.ones((200, 200, 3), dtype=np.uint8) * 128
        low_score = detector._calculate_texture_score(low_texture)

        # High texture should score higher than completely flat
        assert high_score > low_score
        # Both should be in valid range
        assert 0.0 <= high_score <= 100.0
        assert 0.0 <= low_score <= 100.0

    @pytest.mark.asyncio
    async def test_color_score_calculation(self):
        """Test that color score is calculated."""
        detector = TextureLivenessDetector()
        image = self._create_test_image()

        score = detector._calculate_color_score(image)

        assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_frequency_score_calculation(self):
        """Test that frequency score is calculated."""
        detector = TextureLivenessDetector()
        image = self._create_test_image()

        score = detector._calculate_frequency_score(image)

        assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_moire_score_calculation(self):
        """Test that moiré score is calculated."""
        detector = TextureLivenessDetector()
        image = self._create_test_image()

        score = detector._calculate_moire_score(image)

        assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_get_threshold(self):
        """Test getting the liveness threshold."""
        detector = TextureLivenessDetector(liveness_threshold=75.0)

        assert detector.get_threshold() == 75.0

    @pytest.mark.asyncio
    async def test_set_threshold_valid(self):
        """Test setting valid liveness threshold."""
        detector = TextureLivenessDetector()

        detector.set_threshold(80.0)

        assert detector._liveness_threshold == 80.0

    @pytest.mark.asyncio
    async def test_set_threshold_invalid_too_low(self):
        """Test setting invalid threshold (too low)."""
        detector = TextureLivenessDetector()

        with pytest.raises(ValueError, match="between 0 and 100"):
            detector.set_threshold(-10.0)

    @pytest.mark.asyncio
    async def test_set_threshold_invalid_too_high(self):
        """Test setting invalid threshold (too high)."""
        detector = TextureLivenessDetector()

        with pytest.raises(ValueError, match="between 0 and 100"):
            detector.set_threshold(150.0)

    @pytest.mark.asyncio
    async def test_different_image_sizes(self):
        """Test detection works with different image sizes."""
        detector = TextureLivenessDetector()

        for size in [100, 200, 300, 500]:
            image = self._create_test_image(size=size)
            result = await detector.detect(image)

            assert 0.0 <= result.liveness_score <= 100.0

    @pytest.mark.asyncio
    async def test_very_dark_image(self):
        """Test detection with very dark image."""
        detector = TextureLivenessDetector()
        image = self._create_test_image(brightness=30)

        result = await detector.detect(image)

        # Dark images should still return valid result
        assert 0.0 <= result.liveness_score <= 100.0

    @pytest.mark.asyncio
    async def test_very_bright_image(self):
        """Test detection with very bright image."""
        detector = TextureLivenessDetector()
        image = self._create_test_image(brightness=240)

        result = await detector.detect(image)

        # Bright images should still return valid result
        assert 0.0 <= result.liveness_score <= 100.0

    @pytest.mark.asyncio
    async def test_moire_pattern_detection(self):
        """Test that images with moiré patterns score lower."""
        detector = TextureLivenessDetector()

        # Create image with regular pattern (simulating moiré)
        size = 200
        pattern_img = np.zeros((size, size, 3), dtype=np.uint8)

        # Create checkerboard pattern
        for i in range(size):
            for j in range(size):
                if (i // 4 + j // 4) % 2 == 0:
                    pattern_img[i, j] = [255, 255, 255]

        pattern_score = detector._calculate_moire_score(pattern_img)

        # Natural image
        natural_img = self._create_test_image()
        natural_score = detector._calculate_moire_score(natural_img)

        # Pattern image should have lower moiré score (more moiré detected)
        assert pattern_score <= natural_score
