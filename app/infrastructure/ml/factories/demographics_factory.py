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
    ) -> IDemographicsAnalyzer:
        """Create demographics analyzer instance.

        Args:
            backend: Backend to use for analysis
            include_race: Whether to include race estimation
            include_emotion: Whether to include emotion analysis

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
            )

        raise ValueError(f"Unknown demographics backend: {backend}")
