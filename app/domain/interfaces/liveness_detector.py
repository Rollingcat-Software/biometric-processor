"""Liveness detector interface."""

from typing import Protocol
import numpy as np
from app.domain.entities.liveness_result import LivenessResult


class ILivenessDetector(Protocol):
    """Protocol for liveness detection implementations.

    Implementations can use different techniques (smile, blink, head movement, etc.)
    without changing client code (Open/Closed Principle).
    """

    async def check_liveness(self, image: np.ndarray) -> LivenessResult:
        """Check if image shows a live person.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            LivenessResult containing liveness score and challenge information

        Raises:
            FaceNotDetectedError: When no face is found
            LivenessCheckError: When liveness check fails

        Note:
            The specific challenge (smile, blink, etc.) depends on implementation.
            Liveness score range: 0-100 (higher = more likely live person).
        """
        ...

    def get_challenge_type(self) -> str:
        """Get the type of liveness challenge used.

        Returns:
            Challenge type (e.g., "smile", "blink", "head_movement")
        """
        ...

    def get_liveness_threshold(self) -> float:
        """Get the threshold for considering result as live.

        Returns:
            Liveness score threshold (0-100)
        """
        ...
