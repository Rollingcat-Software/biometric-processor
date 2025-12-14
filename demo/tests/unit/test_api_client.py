"""Unit tests for API client module.

Tests the HTTPAPIClient and MockAPIClient in utils/api_client.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from utils.api_client import HTTPAPIClient, MockAPIClient
from utils.exceptions import APIConnectionError, APIResponseError, RateLimitExceededError


class TestMockAPIClient:
    """Tests for MockAPIClient class."""

    def test_initialization(self) -> None:
        """Test client initialization."""
        client = MockAPIClient()
        assert client.base_url == "http://mock-api:8001"

    def test_custom_base_url(self) -> None:
        """Test client with custom base URL."""
        client = MockAPIClient(base_url="http://custom:9000")
        assert client.base_url == "http://custom:9000"

    @pytest.mark.asyncio
    async def test_get_default_response(self) -> None:
        """Test GET returns default response."""
        client = MockAPIClient()
        result = await client.get("/test")
        assert result == {"mock": True}

    @pytest.mark.asyncio
    async def test_get_custom_response(self) -> None:
        """Test GET returns custom response when set."""
        client = MockAPIClient()
        client.set_response("/test", {"custom": "response"})

        result = await client.get("/test")
        assert result == {"custom": "response"}

    @pytest.mark.asyncio
    async def test_post_records_call(self) -> None:
        """Test POST records the call."""
        client = MockAPIClient()
        await client.post("/enroll", data={"user_id": "test"})

        calls = client.get_calls()
        assert len(calls) == 1
        assert calls[0]["method"] == "POST"
        assert calls[0]["endpoint"] == "/enroll"
        assert calls[0]["data"] == {"user_id": "test"}

    @pytest.mark.asyncio
    async def test_delete_records_call(self) -> None:
        """Test DELETE records the call."""
        client = MockAPIClient()
        await client.delete("/webhooks/123")

        calls = client.get_calls()
        assert len(calls) == 1
        assert calls[0]["method"] == "DELETE"
        assert calls[0]["endpoint"] == "/webhooks/123"

    @pytest.mark.asyncio
    async def test_patch_records_call(self) -> None:
        """Test PATCH records the call."""
        client = MockAPIClient()
        await client.patch("/sessions/123", data={"status": "ended"})

        calls = client.get_calls()
        assert len(calls) == 1
        assert calls[0]["method"] == "PATCH"
        assert calls[0]["data"] == {"status": "ended"}

    def test_clear_calls(self) -> None:
        """Test clearing recorded calls."""
        client = MockAPIClient()
        client._calls = [{"method": "GET", "endpoint": "/test"}]

        client.clear_calls()
        assert client.get_calls() == []

    def test_health_check_always_true(self) -> None:
        """Test health check returns True."""
        client = MockAPIClient()
        assert client.health_check() is True

    @pytest.mark.asyncio
    async def test_multiple_responses(self) -> None:
        """Test setting multiple endpoint responses."""
        client = MockAPIClient()
        client.set_response("/health", {"status": "healthy"})
        client.set_response("/enroll", {"success": True})

        health = await client.get("/health")
        enroll = await client.post("/enroll")

        assert health == {"status": "healthy"}
        assert enroll == {"success": True}


class TestHTTPAPIClient:
    """Tests for HTTPAPIClient class."""

    def test_initialization_defaults(self) -> None:
        """Test client initialization with defaults."""
        client = HTTPAPIClient()
        assert client.base_url == "http://localhost:8001"

    def test_initialization_custom(self) -> None:
        """Test client initialization with custom values."""
        client = HTTPAPIClient(
            base_url="http://custom:9000",
            timeout=60,
            api_key="test-key",
        )
        assert client.base_url == "http://custom:9000"
        assert client._timeout == 60
        assert client._api_key == "test-key"

    def test_get_headers_without_api_key(self) -> None:
        """Test header generation without API key."""
        client = HTTPAPIClient()
        headers = client._get_headers()

        assert "Accept" in headers
        assert headers["Accept"] == "application/json"
        assert "Authorization" not in headers

    def test_get_headers_with_api_key(self) -> None:
        """Test header generation with API key."""
        client = HTTPAPIClient(api_key="test-api-key")
        headers = client._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-api-key"

    def test_get_headers_with_extra(self) -> None:
        """Test header generation with extra headers."""
        client = HTTPAPIClient()
        headers = client._get_headers(extra_headers={"X-Custom": "value"})

        assert headers["X-Custom"] == "value"


class TestHTTPAPIClientResponseHandling:
    """Tests for HTTPAPIClient response handling."""

    def test_handle_response_rate_limit(self) -> None:
        """Test rate limit response handling."""
        from unittest.mock import MagicMock

        client = HTTPAPIClient()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with pytest.raises(RateLimitExceededError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.retry_after == 60

    def test_handle_response_error(self) -> None:
        """Test error response handling."""
        from unittest.mock import MagicMock

        client = HTTPAPIClient()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not found"}

        with pytest.raises(APIResponseError) as exc_info:
            client._handle_response(mock_response)

        assert exc_info.value.status_code == 404
        assert "Not found" in exc_info.value.response_body["detail"]

    def test_handle_response_success(self) -> None:
        """Test successful response handling."""
        from unittest.mock import MagicMock

        client = HTTPAPIClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        result = client._handle_response(mock_response)
        assert result == {"status": "healthy"}

    def test_handle_response_non_json(self) -> None:
        """Test handling of non-JSON response."""
        from unittest.mock import MagicMock

        client = HTTPAPIClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"

        result = client._handle_response(mock_response)
        assert result == {"raw": "Plain text response"}
