"""File storage related errors."""

from app.domain.exceptions.base import BiometricProcessorError


class FileStorageError(BiometricProcessorError):
    """Raised when file storage operation fails.

    This can include:
    - Failed to save file
    - Failed to read file
    - Failed to delete file
    - File not found
    - Permission errors
    - Disk space errors
    """

    def __init__(self, operation: str, file_path: str = "", reason: str = "Unknown error") -> None:
        """Initialize file storage error.

        Args:
            operation: Operation that failed (e.g., "save", "read", "delete")
            file_path: Path to file (optional, may contain sensitive info)
            reason: Detailed reason for failure
        """
        # Don't include full file_path in message (may contain sensitive info)
        super().__init__(
            message=f"File storage operation '{operation}' failed: {reason}",
            error_code="FILE_STORAGE_ERROR",
        )
        self.operation = operation
        self.file_path = file_path
        self.reason = reason

    def to_dict(self) -> dict:
        """Include operation and reason in error response.

        Note: file_path is intentionally excluded from API response
        for security reasons (may contain sensitive paths).
        """
        result = super().to_dict()
        result["operation"] = self.operation
        result["reason"] = self.reason
        return result
