"""Cosine similarity calculator implementation."""

import logging
from typing import Optional

import numpy as np


logger = logging.getLogger(__name__)


class CosineSimilarityCalculator:
    """Cosine similarity calculator for face embeddings.

    Implements ISimilarityCalculator using cosine distance metric.
    This is the most common metric for face recognition.

    Following Strategy Pattern: Can be swapped with other similarity
    calculators (Euclidean, Manhattan, etc.) without changing client code.

    Cosine Distance:
    - 0.0 = Identical faces
    - 0.4 = Very similar (high confidence match)
    - 0.6 = Similar (default threshold)
    - 0.8 = Different faces
    - 1.0 = Completely opposite
    """

    def __init__(self, threshold: float = 0.6) -> None:
        """Initialize cosine similarity calculator.

        Args:
            threshold: Distance threshold for considering embeddings a match
                Recommended values:
                - 0.4: High security (1% FAR - False Acceptance Rate)
                - 0.6: Balanced (0.1% FAR) - Default
                - 0.7: Low security (10% FAR)

        Note:
            Lower threshold = stricter matching = fewer false accepts
            Higher threshold = looser matching = more false accepts
        """
        self._threshold = threshold

        logger.info(f"Initialized CosineSimilarityCalculator with threshold={threshold}")

    def calculate(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine distance between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine distance (0.0 = identical, 1.0 = opposite)

        Raises:
            ValueError: If embeddings have different dimensions

        Note:
            Cosine distance = 1 - cosine similarity
            Lower distance indicates higher similarity
        """
        # Validate dimensions
        if len(embedding1) != len(embedding2):
            raise ValueError(
                f"Embedding dimension mismatch: {len(embedding1)} vs {len(embedding2)}"
            )

        # L2 normalize (in case not already normalized)
        emb1_norm = self._l2_normalize(embedding1)
        emb2_norm = self._l2_normalize(embedding2)

        # Calculate cosine similarity
        cosine_similarity = np.dot(emb1_norm, emb2_norm)

        # Convert to distance (0 = identical, 1 = opposite)
        # Clamp to [0, 1] to handle numerical precision issues
        cosine_distance = 1.0 - cosine_similarity
        cosine_distance = np.clip(cosine_distance, 0.0, 1.0)

        distance = float(cosine_distance)

        logger.debug(
            f"Cosine distance: {distance:.4f} "
            f"(threshold: {self._threshold}, "
            f"match: {distance < self._threshold})"
        )

        return distance

    def get_threshold(self) -> float:
        """Get the distance threshold for considering embeddings a match.

        Returns:
            Threshold value
        """
        return self._threshold

    def get_metric_name(self) -> str:
        """Get the name of the similarity metric.

        Returns:
            Metric name
        """
        return "cosine"

    def set_threshold(self, threshold: float) -> None:
        """Set a new distance threshold.

        Args:
            threshold: New threshold value (0.0-1.0)

        Raises:
            ValueError: If threshold is not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be 0.0-1.0, got {threshold}")

        self._threshold = threshold
        logger.info(f"Updated threshold to {threshold}")

    def is_match(self, embedding1: np.ndarray, embedding2: np.ndarray) -> bool:
        """Check if two embeddings match based on threshold.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            True if distance < threshold (match)
        """
        distance = self.calculate(embedding1, embedding2)
        return distance < self._threshold

    def get_confidence(self, distance: float, threshold: Optional[float] = None) -> float:
        """Convert distance to a threshold-anchored confidence score (0.0-1.0).

        The naive ``1 - distance`` mapping under-reports strong matches because
        the operational accept band lives in the low-distance region: with the
        default 0.6 threshold an *excellent* match at distance 0.26 would read a
        scary 74%, and the accept boundary itself reads only ~40%. The matching
        decision is unchanged — only the reported number was misleading.

        This maps the accept boundary to ~50% and an identical match to 100%,
        anchored on the SAME threshold used for the accept/reject decision::

            confidence = clamp01(1 - distance / (2 * threshold))

        - distance = 0          -> 1.0  (identical)
        - distance = threshold  -> 0.5  (accept boundary)
        - distance > threshold  -> < 0.5 (rejected region)

        Args:
            distance: Cosine distance (>= 0.0; pgvector cosine distance is [0, 2])
            threshold: Accept/reject distance threshold to anchor on. Defaults to
                this calculator's configured threshold. Pass the *effective*
                threshold the caller used for the decision (e.g. the adaptive
                aged-embedding threshold) so the reported % stays consistent with
                the verdict.

        Returns:
            Confidence score (0.0-1.0), higher = more confident
        """
        anchor = self._threshold if threshold is None else threshold
        # Guard against a zero/negative anchor producing a div-by-zero / inverted
        # scale; fall back to the legacy inverse mapping in that pathological case.
        if anchor <= 0.0:
            confidence = 1.0 - distance
        else:
            confidence = 1.0 - distance / (2.0 * anchor)
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _l2_normalize(embedding: np.ndarray) -> np.ndarray:
        """L2 normalize an embedding vector.

        Args:
            embedding: Embedding vector

        Returns:
            L2-normalized embedding
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            # Handle zero vector (shouldn't happen in practice)
            return embedding
        return embedding / norm
