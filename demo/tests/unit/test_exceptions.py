"""Unit tests for custom exception classes.

Tests the exception hierarchy defined in utils/exceptions.py.
"""

from __future__ import annotations

import pytest

from utils.exceptions import (
    APIConnectionError,
    APIResponseError,
    ConfigurationError,
    DemoAppError,
    ImageValidationError,
    RateLimitExceededError,
    SessionExpiredError,
    WebSocketError,
)


class TestDemoAppError:
    """Tests for base DemoAppError class."""

    def test_init_with_all_parameters(self) -> None:
        """Test initialization with all parameters."""
        error = DemoAppError(
            message="Test error",
            code="TEST_ERROR",
            details={"key": "value"},
        )

        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.details == {"key": "value"}

    def test_init_with_minimal_parameters(self) -> None:
        """Test initialization with minimal parameters."""
        error = DemoAppError(message="Test", code="TEST")

        assert error.message == "Test"
        assert error.code == "TEST"
        assert error.details == {}

    def test_to_user_message(self) -> None:
        """Test user message generation."""
        error = DemoAppError(message="User friendly message", code="TEST")
        assert error.to_user_message() == "User friendly message"

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        error = DemoAppError(
            message="Test",
            code="TEST",
            details={"key": "value"},
        )
        result = error.to_dict()

        assert result == {
            "code": "TEST",
            "message": "Test",
            "details": {"key": "value"},
        }

    def test_repr(self) -> None:
        """Test string representation."""
        error = DemoAppError(message="Test", code="TEST")
        repr_str = repr(error)

        assert "DemoAppError" in repr_str
        assert "TEST" in repr_str


class TestAPIConnectionError:
    """Tests for APIConnectionError class."""

    def test_default_initialization(self) -> None:
        """Test default initialization without URL."""
        error = APIConnectionError()

        assert error.code == "API_CONNECTION_ERROR"
        assert "Cannot connect" in error.message
        assert error.url is None

    def test_initialization_with_url(self) -> None:
        """Test initialization with URL."""
        error = APIConnectionError(url="http://localhost:8001/api/v1/health")

        assert error.url == "http://localhost:8001/api/v1/health"
        assert error.details["url"] == "http://localhost:8001/api/v1/health"

    def test_user_message_without_url(self) -> None:
        """Test user message when URL is not provided."""
        error = APIConnectionError()
        message = error.to_user_message()

        assert "Cannot connect" in message
        assert "8001" in message

    def test_user_message_with_url(self) -> None:
        """Test user message when URL is provided."""
        error = APIConnectionError(url="http://example.com/api")
        message = error.to_user_message()

        assert "example.com" in message


class TestAPIResponseError:
    """Tests for APIResponseError class."""

    def test_initialization(self) -> None:
        """Test initialization with status code and response."""
        error = APIResponseError(
            status_code=404,
            response_body={"detail": "User not found"},
        )

        assert error.status_code == 404
        assert error.response_body == {"detail": "User not found"}
        assert error.code == "API_RESPONSE_ERROR"

    @pytest.mark.parametrize(
        "status_code,expected_text",
        [
            (400, "Invalid request"),
            (401, "Authentication required"),
            (403, "Access denied"),
            (404, "Not found"),
            (422, "Validation error"),
            (429, "Too many requests"),
            (500, "Server error"),
            (503, "temporarily unavailable"),
        ],
    )
    def test_user_messages_for_status_codes(
        self,
        status_code: int,
        expected_text: str,
    ) -> None:
        """Test user messages for different status codes."""
        error = APIResponseError(
            status_code=status_code,
            response_body={"detail": "Test detail"},
        )
        message = error.to_user_message()

        assert expected_text in message


class TestImageValidationError:
    """Tests for ImageValidationError class."""

    def test_initialization(self) -> None:
        """Test initialization with reason."""
        error = ImageValidationError(reason="No face detected")

        assert error.reason == "No face detected"
        assert error.code == "IMAGE_VALIDATION_ERROR"
        assert "No face detected" in error.message

    @pytest.mark.parametrize(
        "reason,expected_text",
        [
            ("invalid_format", "JPEG or PNG"),
            ("too_large", "too large"),
            ("no_face", "No face detected"),
            ("low_quality", "quality is too low"),
        ],
    )
    def test_user_messages_for_reasons(
        self,
        reason: str,
        expected_text: str,
    ) -> None:
        """Test user messages for different validation reasons."""
        error = ImageValidationError(reason=reason)
        message = error.to_user_message()

        assert expected_text in message


class TestWebSocketError:
    """Tests for WebSocketError class."""

    def test_initialization(self) -> None:
        """Test initialization with reason."""
        error = WebSocketError(reason="Connection closed")

        assert error.reason == "Connection closed"
        assert error.code == "WEBSOCKET_ERROR"

    @pytest.mark.parametrize(
        "reason,expected_text",
        [
            ("connection closed", "lost"),
            ("timeout occurred", "timed out"),
            ("connection refused", "ensure the server"),
        ],
    )
    def test_user_messages_for_reasons(
        self,
        reason: str,
        expected_text: str,
    ) -> None:
        """Test user messages for different WebSocket errors."""
        error = WebSocketError(reason=reason)
        message = error.to_user_message()

        assert expected_text in message


class TestSessionExpiredError:
    """Tests for SessionExpiredError class."""

    def test_initialization(self) -> None:
        """Test initialization with session ID."""
        error = SessionExpiredError(session_id="session-123")

        assert error.session_id == "session-123"
        assert error.code == "SESSION_EXPIRED"
        assert "session-123" in error.details["session_id"]

    def test_user_message(self) -> None:
        """Test user-friendly message."""
        error = SessionExpiredError(session_id="test")
        message = error.to_user_message()

        assert "expired" in message
        assert "new session" in message


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError class."""

    def test_initialization(self) -> None:
        """Test initialization with retry_after."""
        error = RateLimitExceededError(retry_after=60)

        assert error.retry_after == 60
        assert error.code == "RATE_LIMIT_EXCEEDED"

    def test_initialization_with_limit(self) -> None:
        """Test initialization with rate limit value."""
        error = RateLimitExceededError(retry_after=60, limit=100)

        assert error.limit == 100
        assert error.details["limit"] == 100

    def test_user_message_seconds(self) -> None:
        """Test user message for short wait time."""
        error = RateLimitExceededError(retry_after=30)
        message = error.to_user_message()

        assert "30 seconds" in message

    def test_user_message_minutes(self) -> None:
        """Test user message for long wait time."""
        error = RateLimitExceededError(retry_after=120)
        message = error.to_user_message()

        assert "2 minute" in message


class TestConfigurationError:
    """Tests for ConfigurationError class."""

    def test_initialization(self) -> None:
        """Test initialization with setting and reason."""
        error = ConfigurationError(
            setting="API_BASE_URL",
            reason="Required setting is missing",
        )

        assert error.setting == "API_BASE_URL"
        assert error.code == "CONFIGURATION_ERROR"
        assert "API_BASE_URL" in error.message

    def test_user_message(self) -> None:
        """Test user-friendly message."""
        error = ConfigurationError(setting="TEST", reason="Invalid")
        message = error.to_user_message()

        assert "configuration error" in message.lower()
        assert "TEST" in message
