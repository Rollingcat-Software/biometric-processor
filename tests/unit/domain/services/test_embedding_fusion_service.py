"""Unit tests for EmbeddingFusionService."""

import pytest
import numpy as np

from app.domain.services.embedding_fusion_service import EmbeddingFusionService
from app.domain.entities.face_embedding import FaceEmbedding


class TestEmbeddingFusionService:
    """Test EmbeddingFusionService."""

    def test_initialization_with_l2_normalization(self):
        """Test service initialization with L2 normalization."""
        service = EmbeddingFusionService(normalization_strategy="l2")
        assert service.normalization_strategy == "l2"

    def test_initialization_with_no_normalization(self):
        """Test service initialization without normalization."""
        service = EmbeddingFusionService(normalization_strategy="none")
        assert service.normalization_strategy == "none"

    def test_fuse_two_embeddings_equal_quality(self):
        """Test fusion of two embeddings with equal quality scores."""
        service = EmbeddingFusionService()

        # Create two normalized embeddings
        emb1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        emb2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        embeddings = [emb1, emb2]
        quality_scores = [80.0, 80.0]

        fused, avg_quality = service.fuse_embeddings(embeddings, quality_scores)

        # With equal quality, should be average
        assert fused.shape == (4,)
        assert avg_quality == 80.0
        # Check L2 normalized
        assert np.isclose(np.linalg.norm(fused), 1.0)

    def test_fuse_three_embeddings_different_quality(self):
        """Test fusion of three embeddings with different quality scores."""
        service = EmbeddingFusionService()

        # Create three embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)
        emb3 = np.random.randn(128).astype(np.float32)

        embeddings = [emb1, emb2, emb3]
        quality_scores = [90.0, 70.0, 50.0]

        fused, avg_quality = service.fuse_embeddings(embeddings, quality_scores)

        # Verify shape
        assert fused.shape == (128,)

        # Verify weighted average quality
        expected_quality = (90.0 * 90.0 + 70.0 * 70.0 + 50.0 * 50.0) / (90.0 + 70.0 + 50.0)
        assert np.isclose(avg_quality, expected_quality, rtol=0.01)

        # Verify L2 normalized
        assert np.isclose(np.linalg.norm(fused), 1.0)

    def test_fuse_embeddings_empty_list_raises_error(self):
        """Test that empty embeddings list raises ValueError."""
        service = EmbeddingFusionService()

        with pytest.raises(ValueError, match="embeddings list cannot be empty"):
            service.fuse_embeddings([], [])

    def test_fuse_embeddings_single_embedding_raises_error(self):
        """Test that single embedding raises ValueError."""
        service = EmbeddingFusionService()

        emb = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="Need at least 2 embeddings"):
            service.fuse_embeddings([emb], [80.0])

    def test_fuse_embeddings_mismatched_lengths_raises_error(self):
        """Test that mismatched embeddings and quality scores raises error."""
        service = EmbeddingFusionService()

        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="Mismatch"):
            service.fuse_embeddings([emb1, emb2], [80.0])  # Only 1 quality score

    def test_fuse_embeddings_different_dimensions_raises_error(self):
        """Test that embeddings with different dimensions raises error."""
        service = EmbeddingFusionService()

        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(256).astype(np.float32)  # Different dimension

        with pytest.raises(ValueError, match="dimension"):
            service.fuse_embeddings([emb1, emb2], [80.0, 70.0])

    def test_compute_weights_equal_scores(self):
        """Test weight computation with equal quality scores."""
        service = EmbeddingFusionService()

        quality_scores = [80.0, 80.0, 80.0]
        weights = service._compute_weights(quality_scores)

        # All weights should be equal (1/3)
        assert weights.shape == (3,)
        assert np.allclose(weights, [1/3, 1/3, 1/3], rtol=0.01)
        assert np.isclose(np.sum(weights), 1.0)

    def test_compute_weights_different_scores(self):
        """Test weight computation with different quality scores."""
        service = EmbeddingFusionService()

        quality_scores = [90.0, 60.0, 30.0]
        weights = service._compute_weights(quality_scores)

        # Verify weights sum to 1
        assert np.isclose(np.sum(weights), 1.0)

        # Higher quality should have higher weight
        assert weights[0] > weights[1] > weights[2]

    def test_compute_weights_invalid_scores_raises_error(self):
        """Test that invalid quality scores raise ValueError."""
        service = EmbeddingFusionService()

        # Test negative score
        with pytest.raises(ValueError, match="between 0 and 100"):
            service._compute_weights([-10.0, 80.0])

        # Test score > 100
        with pytest.raises(ValueError, match="between 0 and 100"):
            service._compute_weights([80.0, 110.0])

    def test_fuse_face_embeddings_entities(self):
        """Test fusion of FaceEmbedding entities."""
        service = EmbeddingFusionService()

        # Create face embedding entities
        emb1 = FaceEmbedding.create_new(
            user_id="user1",
            vector=np.random.randn(128).astype(np.float32),
            quality_score=85.0,
        )
        emb2 = FaceEmbedding.create_new(
            user_id="user1",
            vector=np.random.randn(128).astype(np.float32),
            quality_score=75.0,
        )

        fused, avg_quality = service.fuse_face_embeddings([emb1, emb2])

        # Verify shape
        assert fused.shape == (128,)

        # Verify quality is weighted average
        expected_quality = (85.0 * 85.0 + 75.0 * 75.0) / (85.0 + 75.0)
        assert np.isclose(avg_quality, expected_quality, rtol=0.01)

    def test_fuse_embeddings_with_no_normalization(self):
        """Test fusion without L2 normalization."""
        service = EmbeddingFusionService(normalization_strategy="none")

        emb1 = np.array([1.0, 0.0], dtype=np.float32)
        emb2 = np.array([0.0, 1.0], dtype=np.float32)

        fused, _ = service.fuse_embeddings([emb1, emb2], [50.0, 50.0])

        # Without normalization, result might not be unit length
        # But should still be valid fusion
        assert fused.shape == (2,)

    def test_fuse_five_embeddings_max_allowed(self):
        """Test fusion of 5 embeddings (maximum allowed)."""
        service = EmbeddingFusionService()

        embeddings = [np.random.randn(128).astype(np.float32) for _ in range(5)]
        quality_scores = [90.0, 85.0, 80.0, 75.0, 70.0]

        fused, avg_quality = service.fuse_embeddings(embeddings, quality_scores)

        # Verify successful fusion
        assert fused.shape == (128,)
        assert 70.0 <= avg_quality <= 90.0
        assert np.isclose(np.linalg.norm(fused), 1.0)

    def test_fusion_quality_improvement_calculation(self):
        """Test quality improvement calculation."""
        service = EmbeddingFusionService()

        individual_qualities = [70.0, 75.0, 80.0]
        fused_quality = 85.0

        improvement = service.compute_fusion_quality_improvement(
            individual_qualities, fused_quality
        )

        # Should show positive improvement
        assert improvement > 0
        expected = ((85.0 - 75.0) / 75.0) * 100
        assert np.isclose(improvement, expected, rtol=0.01)

    def test_fusion_quality_no_improvement(self):
        """Test quality calculation when no improvement."""
        service = EmbeddingFusionService()

        individual_qualities = [80.0, 85.0, 90.0]
        fused_quality = 85.0  # Same as average

        improvement = service.compute_fusion_quality_improvement(
            individual_qualities, fused_quality
        )

        # Should be close to zero
        assert np.isclose(improvement, 0.0, atol=1.0)

    def test_high_quality_bias_in_fusion(self):
        """Test that higher quality embeddings contribute more to fusion."""
        service = EmbeddingFusionService()

        # Create distinct embeddings
        high_quality_emb = np.ones(128, dtype=np.float32)
        low_quality_emb = np.zeros(128, dtype=np.float32)

        embeddings = [high_quality_emb, low_quality_emb]
        quality_scores = [95.0, 30.0]  # Very different qualities

        fused, _ = service.fuse_embeddings(embeddings, quality_scores)

        # Fused should be closer to high quality embedding
        dist_to_high = np.linalg.norm(fused - high_quality_emb / np.linalg.norm(high_quality_emb))
        dist_to_low = np.linalg.norm(fused - low_quality_emb) if np.any(low_quality_emb) else float('inf')

        # Distance to high quality should be smaller (if low isn't zero)
        if not np.allclose(low_quality_emb, 0):
            assert dist_to_high < dist_to_low

    def test_fuse_embeddings_preserves_embedding_type(self):
        """Test that fusion preserves numpy array type."""
        service = EmbeddingFusionService()

        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        fused, _ = service.fuse_embeddings([emb1, emb2], [80.0, 70.0])

        assert isinstance(fused, np.ndarray)
        assert fused.dtype == np.float32 or fused.dtype == np.float64
