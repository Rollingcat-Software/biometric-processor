"""Image preprocessor interface."""

from typing import Protocol

import numpy as np

from app.domain.entities.preprocess_result import PreprocessOptions, PreprocessResult


class IImagePreprocessor(Protocol):
    """Interface for image preprocessing.

    Implementations handle image preprocessing tasks like rotation,
    resizing, normalization, and enhancement.
    """

    def preprocess(
        self,
        image: np.ndarray,
        options: PreprocessOptions,
    ) -> PreprocessResult:
        """Preprocess image for face recognition.

        Args:
            image: Input image as numpy array
            options: Preprocessing options

        Returns:
            PreprocessResult with processed image and metadata
        """
        ...

    def auto_rotate(self, image: np.ndarray, exif_data: dict = None) -> tuple:
        """Auto-rotate image based on EXIF orientation.

        Args:
            image: Input image
            exif_data: Optional EXIF data

        Returns:
            Tuple of (rotated_image, rotation_angle)
        """
        ...

    def resize(self, image: np.ndarray, max_size: int) -> np.ndarray:
        """Resize image to fit within max_size.

        Args:
            image: Input image
            max_size: Maximum dimension

        Returns:
            Resized image
        """
        ...

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """Apply histogram equalization.

        Args:
            image: Input image

        Returns:
            Normalized image
        """
        ...
