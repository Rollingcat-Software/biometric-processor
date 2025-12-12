"""Deepfake detector interface."""

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

import numpy as np

from app.domain.entities.proctor_analysis import DeepfakeAnalysisResult


class IDeepfakeDetector(ABC):
    """Interface for deepfake detection.

    Detects synthetic/manipulated faces using multiple techniques:
    - Frequency analysis (DCT artifacts)
    - Texture inconsistency detection
    - Temporal coherence analysis (video)
    - Ensemble model classification
    """

    @abstractmethod
    async def detect(
        self,
        image: np.ndarray,
        session_id: UUID,
    ) -> DeepfakeAnalysisResult:
        """Analyze image for deepfake indicators.

        Args:
            image: BGR image array
            session_id: Session being analyzed

        Returns:
            DeepfakeAnalysisResult with detection outcome
        """
        pass

    @abstractmethod
    async def detect_video(
        self,
        frames: List[np.ndarray],
        session_id: UUID,
    ) -> DeepfakeAnalysisResult:
        """Analyze video frames for temporal deepfake indicators.

        Args:
            frames: List of BGR image arrays
            session_id: Session being analyzed

        Returns:
            DeepfakeAnalysisResult with temporal analysis
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if deepfake detector is available."""
        pass

    @abstractmethod
    def get_detection_methods(self) -> List[str]:
        """Get available detection methods."""
        pass
