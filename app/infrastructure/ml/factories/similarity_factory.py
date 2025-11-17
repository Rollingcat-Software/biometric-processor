"""Factory for creating similarity calculators."""

import logging

from app.domain.interfaces.similarity_calculator import ISimilarityCalculator
from app.infrastructure.ml.similarity.cosine_similarity import CosineSimilarityCalculator

logger = logging.getLogger(__name__)


class SimilarityCalculatorFactory:
    """Factory for creating similarity calculator instances.

    Implements Factory Pattern for creating different similarity calculator implementations.
    This allows adding new calculators without modifying client code (Open/Closed Principle).

    Supported Metrics:
    - cosine: Cosine distance (recommended for face recognition)
    - euclidean: Euclidean distance (future)
    - manhattan: Manhattan distance (future)
    """

    @staticmethod
    def create(metric: str = "cosine", threshold: float = 0.6, **kwargs) -> ISimilarityCalculator:
        """Create a similarity calculator instance.

        Args:
            metric: Similarity metric to use
                Options: "cosine" (only one supported for now)
            threshold: Distance threshold for matching
            **kwargs: Additional arguments passed to calculator constructor

        Returns:
            Similarity calculator instance implementing ISimilarityCalculator

        Raises:
            ValueError: If metric is not supported

        Example:
            ```python
            calculator = SimilarityCalculatorFactory.create("cosine", threshold=0.6)
            ```
        """
        metric = metric.lower()

        logger.info(f"Creating similarity calculator: {metric}, threshold={threshold}")

        if metric == "cosine":
            return CosineSimilarityCalculator(threshold=threshold, **kwargs)
        else:
            raise ValueError(
                f"Unsupported similarity metric: {metric}. "
                f"Supported metrics: cosine"
            )

    @staticmethod
    def get_available_metrics() -> list[str]:
        """Get list of available similarity metrics.

        Returns:
            List of supported metric names
        """
        return ["cosine"]

    @staticmethod
    def get_recommended_metric() -> str:
        """Get recommended metric for face recognition.

        Returns:
            Recommended metric name
        """
        return "cosine"

    @staticmethod
    def get_recommended_threshold(metric: str = "cosine") -> float:
        """Get recommended threshold for a metric.

        Args:
            metric: Metric name

        Returns:
            Recommended threshold value

        Raises:
            ValueError: If metric is not supported
        """
        thresholds = {
            "cosine": 0.6,  # Balanced: 0.1% FAR
        }

        if metric not in thresholds:
            raise ValueError(f"Unknown metric: {metric}")

        return thresholds[metric]
