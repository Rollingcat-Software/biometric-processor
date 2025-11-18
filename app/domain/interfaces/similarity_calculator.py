"""Similarity calculator interface following Strategy Pattern."""

from typing import Protocol

import numpy as np


class ISimilarityCalculator(Protocol):
    """Protocol for embedding similarity calculation strategies.

    Enables different similarity metrics (cosine, euclidean, etc.)
    to be used interchangeably (Strategy Pattern).
    """

    def calculate(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate similarity distance between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Distance value where lower means more similar
            - For cosine distance: 0 = identical, 1 = opposite
            - For euclidean: 0 = identical, higher = more different

        Raises:
            ValueError: If embeddings have different dimensions

        Note:
            Lower distance indicates higher similarity.
            Compare result against threshold to determine match.
        """
        ...

    def get_threshold(self) -> float:
        """Get the distance threshold for considering embeddings a match.

        Returns:
            Threshold value - distances below this indicate a match

        Note:
            Threshold depends on the similarity metric:
            - Cosine distance: typically 0.4-0.7
            - Euclidean distance: typically 0.6-1.0
        """
        ...

    def get_metric_name(self) -> str:
        """Get the name of the similarity metric.

        Returns:
            Metric name (e.g., "cosine", "euclidean", "euclidean_l2")
        """
        ...
