"""Landmark detector factory."""

from typing import Literal

from app.domain.interfaces.landmark_detector import ILandmarkDetector

LandmarkModel = Literal["mediapipe_468", "dlib_68"]


class LandmarkDetectorFactory:
    """Factory for creating landmark detector instances.

    Follows Open/Closed Principle: Add new models without modifying existing code.
    """

    @staticmethod
    def create(model: LandmarkModel = "mediapipe_468") -> ILandmarkDetector:
        """Create landmark detector instance.

        Args:
            model: Landmark model to use

        Returns:
            ILandmarkDetector implementation

        Raises:
            ValueError: If unknown model specified
        """
        if model == "mediapipe_468":
            from app.infrastructure.ml.landmarks.mediapipe_landmarks import (
                MediaPipeLandmarkDetector,
            )

            return MediaPipeLandmarkDetector()

        elif model == "dlib_68":
            # Placeholder for dlib implementation
            raise NotImplementedError("dlib_68 model not yet implemented")

        raise ValueError(f"Unknown landmark model: {model}")
