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

    def __init__(
        self,
        quality_score: float,
        min_threshold: float = 70.0,
        issues: dict = None,
    ) -> None:
        """Initialize poor image quality error.

        Args:
            quality_score: Actual quality score (0-100)
            min_threshold: Minimum acceptable quality score
            issues: Dictionary of specific quality issues detected
        """
        self.quality_score = quality_score
        self.min_threshold = min_threshold
        self.issues = issues or {}

        # Build specific error message based on issues
        message = self._build_message()

        super().__init__(
            message=message,
            error_code="POOR_IMAGE_QUALITY",
        )

    def _build_message(self) -> str:
        """Build descriptive error message based on specific issues."""
        if not self.issues:
            return (
                f"Image quality too low (score: {self.quality_score:.0f}/100, "
                f"minimum: {self.min_threshold:.0f}). Please provide a clearer image "
                "with good lighting and minimal blur."
            )

        issue_messages = []
        for issue_type, details in self.issues.items():
            if issue_type == "face_size":
                size = details.get("size", 0)
                minimum = details.get("minimum", 80)
                issue_messages.append(f"Face too small ({size}px, minimum: {minimum}px)")
            elif issue_type == "blur":
                score = details.get("score", 0)
                threshold = details.get("threshold", 100)
                issue_messages.append(f"Image too blurry (score: {score:.1f}, threshold: {threshold})")
            elif issue_type == "lighting":
                brightness = details.get("brightness", 0)
                issue_messages.append(f"Poor lighting (brightness: {brightness:.0f})")
            elif issue_type == "angle":
                angle = details.get("angle", 0)
                issue_messages.append(f"Face angle too extreme ({angle:.1f}°)")
            else:
                issue_messages.append(details.get("description", str(issue_type)))

        issues_str = "; ".join(issue_messages)
        return f"Image quality check failed: {issues_str}. Overall score: {self.quality_score:.0f}/100."

    def to_dict(self) -> dict:
        """Include quality scores in error response."""
        result = super().to_dict()
        result["quality_score"] = self.quality_score
        result["min_threshold"] = self.min_threshold
        result["issues"] = self.issues
        return result


class FaceNotFoundError(BiometricProcessorError):
    """Raised when a face is not found in the database.

    This typically indicates:
    - User ID not enrolled
    - Embedding not stored
    """

    def __init__(self, user_id: str | None = None) -> None:
        message = "Face not found in database"
        if user_id:
            message = f"Face not found for user: {user_id}"
        super().__init__(
            message=message,
            error_code="FACE_NOT_FOUND",
        )
        self.user_id = user_id

    def to_dict(self) -> dict:
        """Include user_id in error response."""
        result = super().to_dict()
        if self.user_id:
            result["user_id"] = self.user_id
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


class MLModelTimeoutError(BiometricProcessorError):
    """Raised when ML model operation exceeds timeout.

    This prevents requests from hanging indefinitely when ML models
    become unresponsive due to:
    - Model loading issues
    - Resource exhaustion (CPU/GPU/memory)
    - Infrastructure problems
    - Deadlocks in underlying libraries
    """

    def __init__(self, operation: str, timeout_seconds: int) -> None:
        """Initialize ML model timeout error.

        Args:
            operation: Name of the operation that timed out
            timeout_seconds: Configured timeout in seconds
        """
        super().__init__(
            message=f"ML model operation timed out: {operation} exceeded {timeout_seconds}s timeout. "
            f"Please try again or contact support if the issue persists.",
            error_code="ML_MODEL_TIMEOUT",
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds

    def to_dict(self) -> dict:
        """Include timeout details in error response."""
        result = super().to_dict()
        result["operation"] = self.operation
        result["timeout_seconds"] = self.timeout_seconds
        return result
