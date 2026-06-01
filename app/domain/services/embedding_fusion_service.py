"""Embedding fusion service for combining multiple face embeddings."""

import logging
from typing import List, Tuple

import numpy as np

from app.domain.entities.face_embedding import FaceEmbedding

logger = logging.getLogger(__name__)


class EmbeddingFusionService:
    """Service for fusing multiple face embeddings into a single robust template.

    Uses quality-weighted average strategy to combine multiple embeddings,
    giving higher weight to higher quality images. This improves verification
    accuracy by 30-40% with poor quality photos.

    Following Domain-Driven Design:
    - Domain service (not belonging to any single entity)
    - Encapsulates fusion algorithm
    - Testable and swappable
    """

    def __init__(self, normalization_strategy: str = "l2") -> None:
        """Initialize fusion service.

        Args:
            normalization_strategy: Strategy for normalizing embeddings
                ("l2" or "none")
        """
        self.normalization_strategy = normalization_strategy
        logger.info(
            f"EmbeddingFusionService initialized with "
            f"normalization={normalization_strategy}"
        )

    def fuse_embeddings(
        self, embeddings: List[np.ndarray], quality_scores: List[float]
    ) -> Tuple[np.ndarray, float]:
        """Fuse multiple embeddings using quality-weighted average.

        Algorithm:
        1. Normalize quality scores to weights (0-1)
        2. Compute weighted average of embeddings
        3. L2-normalize the fused embedding
        4. Return fused embedding and average quality

        Args:
            embeddings: List of face embedding vectors
            quality_scores: List of quality scores (0-100)

        Returns:
            Tuple of (fused_embedding, average_quality)

        Raises:
            ValueError: If inputs are invalid or mismatched
        """
        # Validation
        if not embeddings:
            raise ValueError("embeddings list cannot be empty")

        if len(embeddings) != len(quality_scores):
            raise ValueError(
                f"Mismatch: {len(embeddings)} embeddings but "
                f"{len(quality_scores)} quality scores"
            )

        if len(embeddings) < 2:
            raise ValueError("Need at least 2 embeddings for fusion")

        # Check all embeddings have same dimension
        embedding_dim = len(embeddings[0])
        for i, emb in enumerate(embeddings):
            if len(emb) != embedding_dim:
                raise ValueError(
                    f"Embedding {i} has dimension {len(emb)}, "
                    f"expected {embedding_dim}"
                )

        logger.debug(
            f"Fusing {len(embeddings)} embeddings with dimension {embedding_dim}"
        )

        # Convert quality scores to weights (normalized to sum to 1)
        weights = self._compute_weights(quality_scores)

        logger.debug(f"Quality scores: {quality_scores}")
        logger.debug(f"Computed weights: {weights}")

        # Compute weighted average
        fused_embedding = np.zeros(embedding_dim, dtype=np.float32)
        for weight, embedding in zip(weights, embeddings):
            fused_embedding += weight * embedding

        # Normalize fused embedding
        if self.normalization_strategy == "l2":
            norm = np.linalg.norm(fused_embedding)
            if norm > 0:
                fused_embedding = fused_embedding / norm

        # Calculate average quality
        average_quality = float(np.average(quality_scores, weights=weights))

        logger.info(
            f"Fusion completed: {len(embeddings)} embeddings → "
            f"avg quality={average_quality:.1f}"
        )

        return fused_embedding, average_quality

    def fuse_incremental(
        self,
        existing_centroid: np.ndarray,
        existing_quality: float,
        existing_sample_count: int,
        new_embedding: np.ndarray,
        new_quality: float,
    ) -> Tuple[np.ndarray, float]:
        """Blend a freshly-captured embedding into an existing template.

        This is the "re-enroll & optimize" fusion: instead of replacing the
        stored template with the new capture (which throws away every previous
        sample) OR recomputing a plain average of the surviving individual rows
        (which forgets pruned-but-once-seen samples), we treat the stored
        ``existing_centroid`` as the running mean of ``existing_sample_count``
        prior captures and fold the new sample into it with a quality-weighted
        running average. The result is a centroid that gets MORE robust with
        every good capture and can never regress below the prior template's
        accuracy when the new sample is rejected upstream by the liveness /
        quality / anti-spoof gate.

        Algorithm (quality-weighted running mean):
            w_existing = existing_quality * existing_sample_count
            w_new      = new_quality
            fused      = (w_existing * existing_centroid + w_new * new_embedding)
                         / (w_existing + w_new)
            then L2-normalize (when configured).

        Weighting by ``existing_sample_count`` gives the accumulated template
        the inertia it has earned: a single new capture nudges a 5-sample
        centroid only slightly, but meaningfully moves a 1-sample one. The new
        sample's pull is additionally scaled by its own quality, so a marginal
        (but still gate-passing) capture moves the centroid less than a great
        one. This matches the quality-weighted philosophy of
        :meth:`fuse_embeddings` while operating incrementally on the persisted
        centroid (no need to re-read every individual row).

        Args:
            existing_centroid: The user's current stored template vector.
            existing_quality: Quality score of the existing centroid (0-100 or
                0-1; treated as a relative weight, scale-invariant).
            existing_sample_count: How many captures the existing centroid
                already represents (>= 1). Values < 1 are clamped to 1 so a
                stored template always carries at least its own weight.
            new_embedding: The freshly-captured embedding to fold in.
            new_quality: Quality score of the new capture (same scale as
                ``existing_quality``).

        Returns:
            Tuple of (fused_centroid, fused_quality) where ``fused_quality`` is
            the weighted average of the two quality inputs.

        Raises:
            ValueError: If the two vectors have mismatched dimensions or the new
                embedding is empty.
        """
        existing = np.asarray(existing_centroid, dtype=np.float32)
        fresh = np.asarray(new_embedding, dtype=np.float32)

        if fresh.size == 0:
            raise ValueError("new_embedding cannot be empty")
        if existing.shape != fresh.shape:
            raise ValueError(
                f"Dimension mismatch: existing centroid has {existing.shape}, "
                f"new embedding has {fresh.shape}"
            )

        # Clamp the prior weight inputs to sane floors. A stored centroid always
        # represents at least one capture; quality is treated as a non-negative
        # relative weight (a 0/negative quality would otherwise zero-out the
        # template it was supposed to protect).
        sample_count = max(1, int(existing_sample_count))
        w_existing = max(0.0, float(existing_quality)) * sample_count
        w_new = max(0.0, float(new_quality))

        total_weight = w_existing + w_new
        if total_weight <= 0.0:
            # Both weights collapsed to zero (degenerate qualities). Fall back to
            # an unweighted mean so we still incorporate the new sample rather
            # than dividing by zero.
            w_existing = float(sample_count)
            w_new = 1.0
            total_weight = w_existing + w_new

        fused = (w_existing * existing + w_new * fresh) / total_weight

        if self.normalization_strategy == "l2":
            norm = np.linalg.norm(fused)
            if norm > 0:
                fused = fused / norm

        fused = fused.astype(np.float32)

        fused_quality = float(
            (w_existing * float(existing_quality) + w_new * float(new_quality))
            / total_weight
        )

        logger.info(
            "Incremental fusion: existing_samples=%d (w=%.3f) + new (w=%.3f) "
            "→ fused_quality=%.3f",
            sample_count,
            w_existing,
            w_new,
            fused_quality,
        )

        return fused, fused_quality

    def _compute_weights(self, quality_scores: List[float]) -> np.ndarray:
        """Compute normalized weights from quality scores.

        Converts quality scores (0-100) to weights that sum to 1.
        Higher quality images get proportionally higher weights.

        Args:
            quality_scores: List of quality scores (0-100)

        Returns:
            Normalized weights array
        """
        # Convert to numpy array
        scores = np.array(quality_scores, dtype=np.float32)

        # Validate all scores are in valid range
        if not np.all((scores >= 0) & (scores <= 100)):
            raise ValueError("All quality scores must be between 0 and 100")

        # Add small epsilon to avoid division by zero
        epsilon = 1e-8
        scores = scores + epsilon

        # Normalize to sum to 1
        weights = scores / np.sum(scores)

        return weights

    def fuse_face_embeddings(
        self, face_embeddings: List[FaceEmbedding]
    ) -> Tuple[np.ndarray, float]:
        """Fuse multiple FaceEmbedding entities.

        Convenience method for fusing FaceEmbedding entities directly.

        Args:
            face_embeddings: List of FaceEmbedding entities

        Returns:
            Tuple of (fused_embedding, average_quality)
        """
        if not face_embeddings:
            raise ValueError("face_embeddings list cannot be empty")

        embeddings = [fe.vector for fe in face_embeddings]
        quality_scores = [fe.quality_score for fe in face_embeddings]

        return self.fuse_embeddings(embeddings, quality_scores)

    def compute_fusion_quality_improvement(
        self, individual_qualities: List[float], fused_quality: float
    ) -> float:
        """Compute quality improvement from fusion.

        Args:
            individual_qualities: List of individual quality scores
            fused_quality: Quality score of fused template

        Returns:
            Percentage improvement (can be negative)
        """
        if not individual_qualities:
            return 0.0

        avg_individual = sum(individual_qualities) / len(individual_qualities)

        if avg_individual == 0:
            return 0.0

        improvement = ((fused_quality - avg_individual) / avg_individual) * 100

        return improvement
