"""Custom exception hierarchy for the Demo Application.

This module defines a structured exception hierarchy that provides:
    - User-friendly error messages
    - Error codes for programmatic handling
    - Detailed context for debugging
    - Graceful degradation support

Exception Hierarchy:
    DemoAppError (base)
    ├── APIConnectionError
    ├── APIResponseError
    ├── ImageValidationError
    ├── WebSocketError
    ├── SessionExpiredError
    ├── RateLimitExceededError
    └── ConfigurationError
"""

from __future__ import annotations

from typing import Any


class DemoAppError(Exception):
    """Base exception for all demo application errors.

    All custom exceptions inherit from this class, enabling:
        - Consistent error handling with single except clause
        - User-friendly message generation
        - Structured error context

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code.
        details: Additional context for debugging.

    Example:
        >>> try:
        ...     raise DemoAppError("Something went wrong", "GENERIC_ERROR")
        ... except DemoAppError as e:
        ...     print(e.to_user_message())
        Something went wrong
    """

    def __init__(
        self,
        message: str,
        code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize DemoAppError.

        Args:
            message: Human-readable error description.
            code: Machine-readable error code (e.g., "API_CONNECTION_ERROR").
            details: Optional dictionary with additional context.
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_user_message(self) -> str:
        """Convert exception to user-friendly message.

        Returns:
            Human-readable message suitable for UI display.
        """
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization.

        Returns:
            Dictionary containing error code, message, and details.
        """
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:
        """Return detailed string representation for debugging."""
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


class APIConnectionError(DemoAppError):
    """Raised when the API server is unreachable.

    This error indicates network-level issues preventing communication
    with the Biometric Processor API.

    Example:
        >>> raise APIConnectionError()
        >>> # Displays: "Cannot connect to Biometric Processor API..."
    """

    def __init__(
        self,
        url: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize APIConnectionError.

        Args:
            url: The API URL that was unreachable.
            details: Additional context (e.g., original exception).
        """
        error_details = details or {}
        if url:
            error_details["url"] = url

        super().__init__(
            message="Cannot connect to Biometric Processor API. Please ensure the server is running.",
            code="API_CONNECTION_ERROR",
            details=error_details,
        )
        self.url = url

    def to_user_message(self) -> str:
        """Return user-friendly connection error message."""
        base_msg = "Cannot connect to Biometric Processor API."
        if self.url:
            return f"{base_msg} (URL: {self.url})"
        return f"{base_msg} Please ensure the server is running on port 8001."


class APIResponseError(DemoAppError):
    """Raised when the API returns an error response.

    This error wraps HTTP error responses from the API, providing
    structured access to status code and response body.

    Attributes:
        status_code: HTTP status code from API response.
        response_body: Parsed JSON response body.

    Example:
        >>> raise APIResponseError(404, {"detail": "User not found"})
    """

    def __init__(
        self,
        status_code: int,
        response_body: dict[str, Any],
    ) -> None:
        """Initialize APIResponseError.

        Args:
            status_code: HTTP status code (e.g., 400, 404, 500).
            response_body: Parsed JSON response from API.
        """
        detail = response_body.get("detail", "Unknown error")
        super().__init__(
            message=f"API error: {detail}",
            code="API_RESPONSE_ERROR",
            details={
                "status_code": status_code,
                "response": response_body,
            },
        )
        self.status_code = status_code
        self.response_body = response_body

    def to_user_message(self) -> str:
        """Return user-friendly API error message."""
        detail = self.response_body.get("detail", "An error occurred")

        # Provide helpful messages for common status codes
        status_messages = {
            400: f"Invalid request: {detail}",
            401: "Authentication required. Please check your API key.",
            403: "Access denied. You don't have permission for this operation.",
            404: f"Not found: {detail}",
            422: f"Validation error: {detail}",
            429: "Too many requests. Please wait before trying again.",
            500: "Server error. Please try again later.",
            503: "Service temporarily unavailable. Please try again later.",
        }

        return status_messages.get(self.status_code, f"API error ({self.status_code}): {detail}")


class ImageValidationError(DemoAppError):
    """Raised when image validation fails.

    This error indicates issues with uploaded images, such as
    invalid format, corrupt data, or no face detected.

    Attributes:
        reason: Specific reason for validation failure.

    Example:
        >>> raise ImageValidationError("No face detected in image")
    """

    def __init__(self, reason: str) -> None:
        """Initialize ImageValidationError.

        Args:
            reason: Specific reason for validation failure.
        """
        super().__init__(
            message=f"Image validation failed: {reason}",
            code="IMAGE_VALIDATION_ERROR",
            details={"reason": reason},
        )
        self.reason = reason

    def to_user_message(self) -> str:
        """Return user-friendly validation error message."""
        # Map technical reasons to user-friendly messages
        reason_messages = {
            "invalid_format": "Please upload a JPEG or PNG image.",
            "too_large": "Image is too large. Maximum size is 10MB.",
            "too_small": "Image is too small. Minimum size is 100x100 pixels.",
            "corrupt": "Image file appears to be corrupted. Please try another file.",
            "no_face": "No face detected in the image. Please ensure your face is clearly visible.",
            "multiple_faces": "Multiple faces detected. Please upload an image with only one face.",
            "low_quality": "Image quality is too low. Please ensure good lighting and focus.",
        }

        for key, msg in reason_messages.items():
            if key in self.reason.lower():
                return msg

        return f"Image validation failed: {self.reason}"


class WebSocketError(DemoAppError):
    """Raised for WebSocket connection and communication issues.

    This error indicates problems with real-time WebSocket connections
    used for proctoring streaming features.

    Example:
        >>> raise WebSocketError("Connection closed unexpectedly")
    """

    def __init__(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize WebSocketError.

        Args:
            reason: Description of what went wrong.
            details: Additional context for debugging.
        """
        super().__init__(
            message=f"WebSocket error: {reason}",
            code="WEBSOCKET_ERROR",
            details=details or {"reason": reason},
        )
        self.reason = reason

    def to_user_message(self) -> str:
        """Return user-friendly WebSocket error message."""
        if "closed" in self.reason.lower():
            return "Connection lost. Please refresh and try again."
        if "timeout" in self.reason.lower():
            return "Connection timed out. Please check your network and try again."
        if "refused" in self.reason.lower():
            return "Cannot establish connection. Please ensure the server is running."
        return f"Connection error: {self.reason}"


class SessionExpiredError(DemoAppError):
    """Raised when a proctoring session has expired or is invalid.

    This error indicates that a proctoring session is no longer active,
    either due to timeout, manual termination, or completion.

    Attributes:
        session_id: The expired session's ID.

    Example:
        >>> raise SessionExpiredError("session-123")
    """

    def __init__(
        self,
        session_id: str,
        reason: str = "Session has expired",
    ) -> None:
        """Initialize SessionExpiredError.

        Args:
            session_id: The expired session's ID.
            reason: Specific reason for expiration.
        """
        super().__init__(
            message=f"Session expired: {reason}",
            code="SESSION_EXPIRED",
            details={"session_id": session_id, "reason": reason},
        )
        self.session_id = session_id

    def to_user_message(self) -> str:
        """Return user-friendly session expiry message."""
        return "Your session has expired. Please start a new session."


class RateLimitExceededError(DemoAppError):
    """Raised when API rate limit is exceeded.

    This error indicates the user has made too many requests
    in a short period and needs to wait before retrying.

    Attributes:
        retry_after: Seconds to wait before retrying.

    Example:
        >>> raise RateLimitExceededError(60)
        >>> # Wait 60 seconds before retrying
    """

    def __init__(
        self,
        retry_after: int,
        limit: int | None = None,
    ) -> None:
        """Initialize RateLimitExceededError.

        Args:
            retry_after: Seconds to wait before retrying.
            limit: The rate limit that was exceeded (requests/minute).
        """
        details: dict[str, Any] = {"retry_after": retry_after}
        if limit:
            details["limit"] = limit

        super().__init__(
            message=f"Rate limit exceeded. Please wait {retry_after} seconds.",
            code="RATE_LIMIT_EXCEEDED",
            details=details,
        )
        self.retry_after = retry_after
        self.limit = limit

    def to_user_message(self) -> str:
        """Return user-friendly rate limit message."""
        if self.retry_after < 60:
            return f"Too many requests. Please wait {self.retry_after} seconds."
        minutes = self.retry_after // 60
        return f"Too many requests. Please wait {minutes} minute(s)."


class ConfigurationError(DemoAppError):
    """Raised when application configuration is invalid.

    This error indicates missing or invalid configuration settings
    required for the application to function.

    Example:
        >>> raise ConfigurationError("API_BASE_URL", "Required setting is missing")
    """

    def __init__(
        self,
        setting: str,
        reason: str,
    ) -> None:
        """Initialize ConfigurationError.

        Args:
            setting: Name of the problematic setting.
            reason: Description of the configuration issue.
        """
        super().__init__(
            message=f"Configuration error for '{setting}': {reason}",
            code="CONFIGURATION_ERROR",
            details={"setting": setting, "reason": reason},
        )
        self.setting = setting

    def to_user_message(self) -> str:
        """Return user-friendly configuration error message."""
        return f"Application configuration error. Please contact support. (Setting: {self.setting})"
