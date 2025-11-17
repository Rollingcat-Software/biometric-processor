"""Unit tests for CosineSimilarityCalculator."""

import pytest
import numpy as np

from app.infrastructure.ml.similarity.cosine_similarity import CosineSimilarityCalculator


class TestCosineSimilarityCalculator:
    """Test CosineSimilarityCalculator."""

    def test_initialization_default_threshold(self):
        """Test initialization with default threshold."""
        calculator = CosineSimilarityCalculator()

        assert calculator.get_threshold() == 0.6
        assert calculator.get_metric_name() == "cosine"

    def test_initialization_custom_threshold(self):
        """Test initialization with custom threshold."""
        calculator = CosineSimilarityCalculator(threshold=0.5)

        assert calculator.get_threshold() == 0.5

    def test_identical_embeddings(self):
        """Test distance between identical embeddings."""
        calculator = CosineSimilarityCalculator()

        # Create identical embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = emb1.copy()

        distance = calculator.calculate(emb1, emb2)

        # Identical embeddings should have distance ~0
        assert distance < 0.01

    def test_orthogonal_embeddings(self):
        """Test distance between orthogonal embeddings."""
        calculator = CosineSimilarityCalculator()

        # Create orthogonal embeddings
        emb1 = np.zeros(128, dtype=np.float32)
        emb1[0] = 1.0

        emb2 = np.zeros(128, dtype=np.float32)
        emb2[1] = 1.0

        distance = calculator.calculate(emb1, emb2)

        # Orthogonal vectors should have distance ~1.0
        assert 0.99 < distance <= 1.0

    def test_similar_embeddings(self):
        """Test distance between similar embeddings."""
        calculator = CosineSimilarityCalculator()

        # Create similar embeddings (same base with small noise)
        base = np.random.randn(128).astype(np.float32)
        emb1 = base + np.random.randn(128).astype(np.float32) * 0.1
        emb2 = base + np.random.randn(128).astype(np.float32) * 0.1

        distance = calculator.calculate(emb1, emb2)

        # Similar embeddings should have low distance
        assert distance < 0.3

    def test_dimension_mismatch_raises_error(self):
        """Test that dimension mismatch raises ValueError."""
        calculator = CosineSimilarityCalculator()

        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(256).astype(np.float32)

        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            calculator.calculate(emb1, emb2)

    def test_set_threshold_valid(self):
        """Test setting valid threshold."""
        calculator = CosineSimilarityCalculator(threshold=0.6)

        calculator.set_threshold(0.5)

        assert calculator.get_threshold() == 0.5

    def test_set_threshold_invalid_too_low(self):
        """Test that threshold below 0 raises ValueError."""
        calculator = CosineSimilarityCalculator()

        with pytest.raises(ValueError, match="Threshold must be 0.0-1.0"):
            calculator.set_threshold(-0.1)

    def test_set_threshold_invalid_too_high(self):
        """Test that threshold above 1 raises ValueError."""
        calculator = CosineSimilarityCalculator()

        with pytest.raises(ValueError, match="Threshold must be 0.0-1.0"):
            calculator.set_threshold(1.5)

    def test_is_match_true(self):
        """Test is_match returns True for matching embeddings."""
        calculator = CosineSimilarityCalculator(threshold=0.6)

        # Create very similar embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = emb1 + np.random.randn(128).astype(np.float32) * 0.01  # Very small noise

        is_match = calculator.is_match(emb1, emb2)

        assert is_match is True

    def test_is_match_false(self):
        """Test is_match returns False for non-matching embeddings."""
        calculator = CosineSimilarityCalculator(threshold=0.4)

        # Create different embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        is_match = calculator.is_match(emb1, emb2)

        # Random embeddings usually don't match with strict threshold
        # This test may occasionally fail due to randomness, but very unlikely
        assert is_match is False

    def test_get_confidence(self):
        """Test converting distance to confidence."""
        calculator = CosineSimilarityCalculator()

        # Low distance = high confidence
        assert calculator.get_confidence(0.1) == 0.9
        assert calculator.get_confidence(0.3) == 0.7
        assert calculator.get_confidence(0.5) == 0.5
        assert calculator.get_confidence(0.0) == 1.0
        assert calculator.get_confidence(1.0) == 0.0

    def test_l2_normalize_unit_vector(self):
        """Test L2 normalization produces unit vectors."""
        calculator = CosineSimilarityCalculator()

        # Create random embedding
        emb = np.random.randn(128).astype(np.float32)

        # Normalize
        normalized = calculator._l2_normalize(emb)

        # Check it's a unit vector (magnitude = 1)
        magnitude = np.linalg.norm(normalized)
        assert abs(magnitude - 1.0) < 1e-6

    def test_l2_normalize_zero_vector(self):
        """Test L2 normalization handles zero vector."""
        calculator = CosineSimilarityCalculator()

        # Zero vector
        emb = np.zeros(128, dtype=np.float32)

        # Should return zero vector (no division by zero)
        normalized = calculator._l2_normalize(emb)

        assert np.all(normalized == 0.0)

    def test_distance_range_clamped(self):
        """Test that distance is clamped to [0, 1]."""
        calculator = CosineSimilarityCalculator()

        # Create embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        distance = calculator.calculate(emb1, emb2)

        # Distance should always be in [0, 1]
        assert 0.0 <= distance <= 1.0

    def test_distance_symmetry(self):
        """Test that distance is symmetric: d(a,b) = d(b,a)."""
        calculator = CosineSimilarityCalculator()

        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        distance1 = calculator.calculate(emb1, emb2)
        distance2 = calculator.calculate(emb2, emb1)

        # Should be exactly equal (not just approximately)
        assert abs(distance1 - distance2) < 1e-7

    def test_calculate_with_normalized_embeddings(self):
        """Test calculation with already-normalized embeddings."""
        calculator = CosineSimilarityCalculator()

        # Create normalized embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb1 = emb1 / np.linalg.norm(emb1)

        emb2 = np.random.randn(128).astype(np.float32)
        emb2 = emb2 / np.linalg.norm(emb2)

        # Should work correctly with pre-normalized embeddings
        distance = calculator.calculate(emb1, emb2)

        assert 0.0 <= distance <= 1.0

    def test_different_dimensions(self):
        """Test calculator works with different embedding dimensions."""
        calculator = CosineSimilarityCalculator()

        # Test with 512-D embeddings (e.g., FaceNet512)
        emb1 = np.random.randn(512).astype(np.float32)
        emb2 = emb1 + np.random.randn(512).astype(np.float32) * 0.1

        distance = calculator.calculate(emb1, emb2)

        # Should still work correctly
        assert 0.0 <= distance <= 1.0
        assert distance < 0.3  # Should be similar
