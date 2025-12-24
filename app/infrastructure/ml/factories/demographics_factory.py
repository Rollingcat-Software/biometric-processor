"""Demographics analyzer factory."""

from typing import Literal

from app.domain.interfaces.demographics_analyzer import IDemographicsAnalyzer

DemographicsBackend = Literal["deepface"]


class DemographicsAnalyzerFactory:
    """Factory for creating demographics analyzer instances.

    Follows Open/Closed Principle: Add new backends without modifying existing code.
    """

    @staticmethod
    def create(
        backend: DemographicsBackend = "deepface",
        include_race: bool = False,
        include_emotion: bool = True,
        min_image_size: int = 224,
        age_margin: int = 10,
        age_confidence: float = 0.65,
    ) -> IDemographicsAnalyzer:
        """Create demographics analyzer instance.

        Args:
            backend: Backend to use for analysis
            include_race: Whether to include race estimation
            include_emotion: Whether to include emotion analysis
            min_image_size: Minimum image size for accurate analysis
            age_margin: Age range margin in years
            age_confidence: Age estimation confidence to report

        Returns:
            IDemographicsAnalyzer implementation

        Raises:
            ValueError: If unknown backend specified
        """
        if backend == "deepface":
            from app.infrastructure.ml.demographics.deepface_demographics import (
                DeepFaceDemographicsAnalyzer,
            )

            return DeepFaceDemographicsAnalyzer(
                include_race=include_race,
                include_emotion=include_emotion,
                min_image_size=min_image_size,
                age_margin=age_margin,
                age_confidence=age_confidence,
            )

        raise ValueError(f"Unknown demographics backend: {backend}")
