"""Face detection and processing related errors."""

from app.domain.exceptions.base import BiometricProcessorError


class FaceNotDetectedError(BiometricProcessorError):
    """Raised when no face is detected in the image.

    This typically indicates:
    - No person in the image
    - Image quality too poor for detection
    - Face too small or partially visible
    - Extreme angles or occlusions
    """

    def __init__(self) -> None:
        super().__init__(
            message="No face detected in the image. Please ensure a clear, front-facing photo.",
            error_code="FACE_NOT_DETECTED",
        )


class MultipleFacesError(BiometricProcessorError):
    """Raised when multiple faces are detected in the image.

    The system expects a single face for enrollment or verification.
    """

    def __init__(self, count: int) -> None:
        """Initialize multiple faces error.

        Args:
            count: Number of faces detected
        """
        super().__init__(
            message=f"Multiple faces detected ({count}). Please provide an image with a single face.",
            error_code="MULTIPLE_FACES",
        )
        self.face_count = count

    def to_dict(self) -> dict:
        """Include face count in error response."""
        result = super().to_dict()
        result["face_count"] = self.face_count
        return result


class PoorImageQualityError(BiometricProcessorError):
    """Raised when image quality is below acceptable threshold.

    Quality issues can include:
    - Excessive blur
    - Poor lighting (too dark or too bright)
    - Face too small
    - Low resolution
    """

    def __init__(self, quality_score: float, min_threshold: float = 70.0) -> None:
        """Initialize poor image quality error.

        Args:
            quality_score: Actual quality score (0-100)
            min_threshold: Minimum acceptable quality score
        """
        super().__init__(
            message=(
                f"Image quality too low (score: {quality_score:.0f}/100, "
                f"minimum: {min_threshold:.0f}). Please provide a clearer image "
                "with good lighting and minimal blur."
            ),
            error_code="POOR_IMAGE_QUALITY",
        )
        self.quality_score = quality_score
        self.min_threshold = min_threshold

    def to_dict(self) -> dict:
        """Include quality scores in error response."""
        result = super().to_dict()
        result["quality_score"] = self.quality_score
        result["min_threshold"] = self.min_threshold
        return result


class EmbeddingExtractionError(BiometricProcessorError):
    """Raised when face embedding extraction fails.

    This is typically an internal error indicating:
    - ML model failure
    - Invalid input to model
    - Resource constraints (memory, GPU)
    """

    def __init__(self, reason: str = "Unknown error") -> None:
        """Initialize embedding extraction error.

        Args:
            reason: Detailed reason for failure
        """
        super().__init__(
            message=f"Failed to extract face embedding: {reason}",
            error_code="EMBEDDING_EXTRACTION_FAILED",
        )
        self.reason = reason

    def to_dict(self) -> dict:
        """Include failure reason in error response."""
        result = super().to_dict()
        result["reason"] = self.reason
        return result
