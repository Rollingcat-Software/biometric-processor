"""Demographics analyzer interface."""

from typing import List, Protocol

import numpy as np

from app.domain.entities.demographics import DemographicsResult


class IDemographicsAnalyzer(Protocol):
    """Interface for demographics analysis.

    Implementations analyze face images to estimate age, gender,
    and optionally race and emotion.
    """

    def analyze(self, image: np.ndarray) -> DemographicsResult:
        """Analyze demographics from face image.

        Args:
            image: Face image as numpy array (RGB format)

        Returns:
            DemographicsResult with age, gender, and optional attributes
        """
        ...

    def get_supported_attributes(self) -> List[str]:
        """Get list of analyzable attributes.

        Returns:
            List of supported attribute names (e.g., ['age', 'gender', 'emotion'])
        """
        ...
