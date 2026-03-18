"""OpenCV-based image preprocessor implementation."""

import logging
from typing import Tuple

import cv2
import numpy as np

from app.domain.entities.preprocess_result import PreprocessOptions, PreprocessResult
from app.domain.exceptions.feature_errors import PreprocessingError

logger = logging.getLogger(__name__)


class OpenCVImagePreprocessor:
    """Image preprocessor using OpenCV.

    Handles image preprocessing tasks like rotation, resizing,
    normalization, and enhancement.
    """

    # EXIF orientation values
    EXIF_ORIENTATIONS = {
        1: 0,    # Normal
        3: 180,  # Upside down
        6: 270,  # Rotated 90 CW
        8: 90,   # Rotated 90 CCW
    }

    def __init__(
        self,
        auto_rotate: bool = True,
        max_size: int = 1920,
        normalize: bool = True,
    ) -> None:
        """Initialize OpenCV image preprocessor.

        Args:
            auto_rotate: Whether to auto-rotate based on EXIF
            max_size: Maximum image dimension
            normalize: Whether to apply normalization
        """
        self._auto_rotate = auto_rotate
        self._max_size = max_size
        self._normalize = normalize
        logger.info(
            f"OpenCVImagePreprocessor initialized: "
            f"auto_rotate={auto_rotate}, max_size={max_size}, normalize={normalize}"
        )

    def preprocess(
        self, image: np.ndarray, options: PreprocessOptions = None
    ) -> PreprocessResult:
        """Preprocess image for face recognition.

        Args:
            image: Input image as numpy array
            options: Preprocessing options (uses defaults if None)

        Returns:
            PreprocessResult with processed image and metadata
        """
        logger.debug("Starting image preprocessing")

        options = options or PreprocessOptions(
            auto_rotate=self._auto_rotate,
            max_size=self._max_size,
            normalize=self._normalize,
        )

        original_size = (image.shape[1], image.shape[0])  # width, height
        operations = []
        was_rotated = False
        rotation_angle = 0

        processed = image.copy()

        try:
            # Auto-rotate (would need EXIF data in practice)
            if options.auto_rotate:
                # In practice, extract EXIF from original file
                pass

            # Resize if needed
            if options.max_size > 0:
                processed, resized = self._resize_if_needed(processed, options.max_size)
                if resized:
                    operations.append("resize")

            # Normalize
            if options.normalize:
                processed = self.normalize(processed)
                operations.append("normalize")

            # Denoise
            if options.denoise:
                processed = cv2.fastNlMeansDenoisingColored(processed, None, 10, 10, 7, 21)
                operations.append("denoise")

            # Color correct
            if options.color_correct:
                processed = self._white_balance(processed)
                operations.append("color_correct")

            new_size = (processed.shape[1], processed.shape[0])

            result = PreprocessResult(
                image=processed,
                original_size=original_size,
                new_size=new_size,
                was_rotated=was_rotated,
                rotation_angle=rotation_angle,
                operations_applied=operations,
            )

            logger.info(
                f"Preprocessing complete: {original_size} -> {new_size}, "
                f"operations={operations}"
            )

            return result

        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            raise PreprocessingError(f"Image preprocessing failed: {str(e)}")

    def auto_rotate(
        self, image: np.ndarray, exif_data: dict = None
    ) -> Tuple[np.ndarray, int]:
        """Auto-rotate image based on EXIF orientation.

        Args:
            image: Input image
            exif_data: Optional EXIF data dictionary

        Returns:
            Tuple of (rotated_image, rotation_angle)
        """
        if not exif_data:
            return image, 0

        orientation = exif_data.get("Orientation", 1)
        angle = self.EXIF_ORIENTATIONS.get(orientation, 0)

        if angle == 0:
            return image, 0

        if angle == 90:
            rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif angle == 180:
            rotated = cv2.rotate(image, cv2.ROTATE_180)
        elif angle == 270:
            rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        else:
            rotated = image

        return rotated, angle

    def resize(self, image: np.ndarray, max_size: int) -> np.ndarray:
        """Resize image to fit within max_size.

        Args:
            image: Input image
            max_size: Maximum dimension

        Returns:
            Resized image
        """
        height, width = image.shape[:2]
        max_dim = max(height, width)

        if max_dim <= max_size:
            return image

        scale = max_size / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)

        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    def _resize_if_needed(
        self, image: np.ndarray, max_size: int
    ) -> Tuple[np.ndarray, bool]:
        """Resize image if larger than max_size."""
        height, width = image.shape[:2]

        if max(height, width) <= max_size:
            return image, False

        return self.resize(image, max_size), True

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """Apply histogram equalization.

        Args:
            image: Input image (RGB)

        Returns:
            Normalized image
        """
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)

        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])

        # Convert back to RGB
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    def _white_balance(self, image: np.ndarray) -> np.ndarray:
        """Apply simple white balance correction."""
        result = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        avg_a = np.average(result[:, :, 1])
        avg_b = np.average(result[:, :, 2])
        result[:, :, 1] = result[:, :, 1] - (
            (avg_a - 128) * (result[:, :, 0] / 255.0) * 1.1
        )
        result[:, :, 2] = result[:, :, 2] - (
            (avg_b - 128) * (result[:, :, 0] / 255.0) * 1.1
        )
        return cv2.cvtColor(result, cv2.COLOR_LAB2RGB)
