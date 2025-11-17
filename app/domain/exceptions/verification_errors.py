"""Face verification related errors."""

from app.domain.exceptions.base import BiometricProcessorError


class EmbeddingNotFoundError(BiometricProcessorError):
    """Raised when no stored embedding is found for the user.

    This indicates the user has not enrolled their face yet.
    """

    def __init__(self, user_id: str) -> None:
        """Initialize embedding not found error.

        Args:
            user_id: User identifier
        """
        super().__init__(
            message=f"No face embedding found for user '{user_id}'. Please enroll first.",
            error_code="EMBEDDING_NOT_FOUND",
        )
        self.user_id = user_id

    def to_dict(self) -> dict:
        """Include user_id in error response."""
        result = super().to_dict()
        result["user_id"] = self.user_id
        return result


class VerificationFailedError(BiometricProcessorError):
    """Raised when face verification fails (faces don't match).

    This is not necessarily an error condition, but indicates
    the verification result is negative.
    """

    def __init__(self, confidence: float, threshold: float) -> None:
        """Initialize verification failed error.

        Args:
            confidence: Actual confidence score (0.0-1.0)
            threshold: Required threshold for verification
        """
        super().__init__(
            message=(
                f"Face verification failed. Confidence {confidence:.2f} "
                f"is below threshold {threshold:.2f}."
            ),
            error_code="VERIFICATION_FAILED",
        )
        self.confidence = confidence
        self.threshold = threshold

    def to_dict(self) -> dict:
        """Include confidence and threshold in error response."""
        result = super().to_dict()
        result["confidence"] = self.confidence
        result["threshold"] = self.threshold
        return result
