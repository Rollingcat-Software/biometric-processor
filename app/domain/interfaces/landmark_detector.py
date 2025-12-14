"""Landmark detector interface."""

from typing import Protocol

import numpy as np

from app.domain.entities.face_landmarks import LandmarkResult


class ILandmarkDetector(Protocol):
    """Interface for facial landmark detection.

    Implementations detect facial landmarks (keypoints) in face images.
    """

    def detect(
        self,
        image: np.ndarray,
        include_3d: bool = False,
    ) -> LandmarkResult:
        """Detect facial landmarks in image.

        Args:
            image: Face image as numpy array (RGB format)
            include_3d: Whether to include 3D coordinates

        Returns:
            LandmarkResult with detected landmarks
        """
        ...

    def get_landmark_count(self) -> int:
        """Get number of landmarks this detector provides.

        Returns:
            Number of landmarks (e.g., 68 for dlib, 468 for MediaPipe)
        """
        ...

    def get_model_name(self) -> str:
        """Get name of the landmark model.

        Returns:
            Model identifier string
        """
        ...
