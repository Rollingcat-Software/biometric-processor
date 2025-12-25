"""Multi-image enrollment related errors."""

from app.domain.exceptions.base import BiometricProcessorError


class EnrollmentSessionError(BiometricProcessorError):
    """Base class for enrollment session errors."""

    pass


class SessionNotFoundError(EnrollmentSessionError):
    """Raised when enrollment session is not found."""

    def __init__(self, session_id: str) -> None:
        """Initialize session not found error.

        Args:
            session_id: The session ID that was not found
        """
        super().__init__(
            message=f"Enrollment session '{session_id}' not found",
            error_code="SESSION_NOT_FOUND",
        )
        self.session_id = session_id


class SessionAlreadyCompletedError(EnrollmentSessionError):
    """Raised when trying to add images to completed session."""

    def __init__(self, session_id: str) -> None:
        """Initialize session already completed error.

        Args:
            session_id: The completed session ID
        """
        super().__init__(
            message=f"Session '{session_id}' is already completed",
            error_code="SESSION_ALREADY_COMPLETED",
        )
        self.session_id = session_id


class SessionFullError(EnrollmentSessionError):
    """Raised when session has reached maximum image limit."""

    def __init__(self, session_id: str, max_images: int) -> None:
        """Initialize session full error.

        Args:
            session_id: The full session ID
            max_images: Maximum images allowed
        """
        super().__init__(
            message=f"Session '{session_id}' already has {max_images} images (maximum)",
            error_code="SESSION_FULL",
        )
        self.session_id = session_id
        self.max_images = max_images


class InsufficientImagesError(EnrollmentSessionError):
    """Raised when trying to fuse with insufficient images."""

    def __init__(self, session_id: str, current: int, minimum: int) -> None:
        """Initialize insufficient images error.

        Args:
            session_id: The session ID
            current: Current number of images
            minimum: Minimum images required
        """
        super().__init__(
            message=(
                f"Session '{session_id}' has only {current} image(s), "
                f"but {minimum} are required for enrollment"
            ),
            error_code="INSUFFICIENT_IMAGES",
        )
        self.session_id = session_id
        self.current_images = current
        self.minimum_images = minimum


class FusionError(EnrollmentSessionError):
    """Raised when embedding fusion fails."""

    def __init__(self, reason: str) -> None:
        """Initialize fusion error.

        Args:
            reason: Reason for fusion failure
        """
        super().__init__(
            message=f"Failed to fuse embeddings: {reason}",
            error_code="FUSION_FAILED",
        )
        self.reason = reason


class InvalidImageCountError(EnrollmentSessionError):
    """Raised when invalid number of images is provided."""

    def __init__(self, count: int, min_images: int, max_images: int) -> None:
        """Initialize invalid image count error.

        Args:
            count: Number of images provided
            min_images: Minimum images required
            max_images: Maximum images allowed
        """
        super().__init__(
            message=(
                f"Invalid number of images: {count}. "
                f"Must provide between {min_images} and {max_images} images"
            ),
            error_code="INVALID_IMAGE_COUNT",
        )
        self.count = count
        self.min_images = min_images
        self.max_images = max_images


class MLModelTimeoutError(EnrollmentSessionError):
    """Raised when ML model operation times out."""

    def __init__(self, operation: str, timeout_seconds: int) -> None:
        """Initialize ML model timeout error.

        Args:
            operation: The operation that timed out (e.g., "face_detection")
            timeout_seconds: The timeout value in seconds
        """
        super().__init__(
            message=(
                f"ML model operation '{operation}' timed out after {timeout_seconds}s. "
                f"This may indicate model unavailability or overload."
            ),
            error_code="ML_MODEL_TIMEOUT",
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds
