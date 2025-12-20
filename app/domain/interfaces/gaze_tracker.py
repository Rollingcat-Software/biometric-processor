"""Gaze tracker interface."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

import numpy as np

from app.domain.entities.proctor_analysis import GazeAnalysisResult, HeadPose


class IGazeTracker(ABC):
    """Interface for gaze tracking analysis."""

    @abstractmethod
    async def analyze(
        self,
        image: np.ndarray,
        session_id: UUID,
    ) -> GazeAnalysisResult:
        """Analyze image for gaze direction and head pose.

        Args:
            image: BGR image array
            session_id: Session being analyzed

        Returns:
            GazeAnalysisResult with head pose and gaze direction
        """
        pass

    @abstractmethod
    async def get_head_pose(
        self,
        image: np.ndarray,
    ) -> Optional[HeadPose]:
        """Get head pose only (faster than full analysis).

        Args:
            image: BGR image array

        Returns:
            HeadPose or None if face not detected
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if gaze tracker is available."""
        pass
