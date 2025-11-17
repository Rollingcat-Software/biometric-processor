"""Base exception for all domain exceptions."""


class BiometricProcessorError(Exception):
    """Base exception for all biometric processor errors.

    All domain exceptions inherit from this class, providing:
    - Consistent error handling
    - Error codes for client identification
    - Human-readable messages

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code for client handling
    """

    def __init__(self, message: str, error_code: str) -> None:
        """Initialize biometric processor error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (uppercase snake_case)
        """
        self.message = message
        self.error_code = error_code
        super().__init__(message)

    def __str__(self) -> str:
        """String representation including error code."""
        return f"[{self.error_code}] {self.message}"

    def __repr__(self) -> str:
        """Repr representation for debugging."""
        return f"{self.__class__.__name__}(message='{self.message}', error_code='{self.error_code}')"

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary with error_code and message
        """
        return {"error_code": self.error_code, "message": self.message}
