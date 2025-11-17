"""Repository and data persistence related errors."""

from app.domain.exceptions.base import BiometricProcessorError


class RepositoryError(BiometricProcessorError):
    """Raised when repository operation fails.

    This is a generic repository error for database or storage failures.
    """

    def __init__(self, operation: str, reason: str = "Unknown error") -> None:
        """Initialize repository error.

        Args:
            operation: Operation that failed (e.g., "save", "find", "delete")
            reason: Detailed reason for failure
        """
        super().__init__(
            message=f"Repository operation '{operation}' failed: {reason}",
            error_code="REPOSITORY_ERROR",
        )
        self.operation = operation
        self.reason = reason

    def to_dict(self) -> dict:
        """Include operation and reason in error response."""
        result = super().to_dict()
        result["operation"] = self.operation
        result["reason"] = self.reason
        return result


class EmbeddingAlreadyExistsError(BiometricProcessorError):
    """Raised when attempting to create an embedding that already exists.

    This can be used for strict enrollment policies where
    re-enrollment requires explicit update.
    """

    def __init__(self, user_id: str) -> None:
        """Initialize embedding already exists error.

        Args:
            user_id: User identifier
        """
        super().__init__(
            message=f"Face embedding already exists for user '{user_id}'. Use update instead.",
            error_code="EMBEDDING_ALREADY_EXISTS",
        )
        self.user_id = user_id

    def to_dict(self) -> dict:
        """Include user_id in error response."""
        result = super().to_dict()
        result["user_id"] = self.user_id
        return result
