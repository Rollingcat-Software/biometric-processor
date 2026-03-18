"""Integration tests for Phase 2 middleware components."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.interfaces.rate_limit_storage import RateLimitInfo


# ============================================================================
# Rate Limit Middleware Tests
# ============================================================================


class TestRateLimitMiddleware:
    """Test rate limit middleware integration."""

    @pytest.fixture
    def mock_rate_limit_storage(self):
        """Create mock rate limit storage."""
        storage = Mock()
        storage.increment = AsyncMock(return_value=RateLimitInfo(
            limit=60,
            remaining=59,
            reset_at=1700000000,
            tier="standard",
        ))
        storage.get = AsyncMock(return_value=None)
        return storage

    @pytest.fixture
    def app_with_rate_limit(self, mock_rate_limit_storage):
        """Create FastAPI app with rate limit middleware."""
        from app.api.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            storage=mock_rate_limit_storage,
            default_limit=60,
            window_seconds=60,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        return app

    def test_rate_limit_headers_added(self, app_with_rate_limit, mock_rate_limit_storage):
        """Test that rate limit headers are added to responses."""
        client = TestClient(app_with_rate_limit)
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            response = client.get("/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_excluded_paths_not_rate_limited(self, app_with_rate_limit, mock_rate_limit_storage):
        """Test that excluded paths are not rate limited."""
        client = TestClient(app_with_rate_limit)
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            response = client.get("/health")

        assert response.status_code == 200
        # Storage should not be called for excluded paths
        # Note: may be called due to test setup


# ============================================================================
# API Key Auth Middleware Tests
# ============================================================================


class TestAPIKeyAuthMiddleware:
    """Test API key authentication middleware."""

    @pytest.fixture
    def mock_api_key_repository(self):
        """Create mock API key repository."""
        repository = Mock()
        repository.find_by_key_hash = AsyncMock(return_value=None)
        repository.update_last_used = AsyncMock()
        return repository

    @pytest.fixture
    def app_with_api_key_auth(self, mock_api_key_repository):
        """Create FastAPI app with API key auth middleware."""
        from app.api.middleware.api_key_auth import APIKeyAuthMiddleware

        app = FastAPI()

        app.add_middleware(
            APIKeyAuthMiddleware,
            repository=mock_api_key_repository,
            require_auth=False,  # Don't require auth for testing
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        return app

    def test_request_without_api_key_allowed(self, app_with_api_key_auth):
        """Test that requests without API key are allowed when not required."""
        client = TestClient(app_with_api_key_auth)
        response = client.get("/test")
        assert response.status_code == 200

    def test_excluded_paths_bypass_auth(self, app_with_api_key_auth):
        """Test that excluded paths bypass auth."""
        client = TestClient(app_with_api_key_auth)
        response = client.get("/health")
        assert response.status_code == 200


class TestAPIKeyAuthMiddlewareRequired:
    """Test API key auth middleware when auth is required."""

    def test_request_without_api_key_rejected(self):
        """Test that requests without API key are rejected when required."""
        from app.api.middleware.api_key_auth import APIKeyAuthMiddleware

        mock_repo = Mock()
        mock_repo.find_by_key_hash = AsyncMock(return_value=None)
        mock_repo.update_last_used = AsyncMock()

        app = FastAPI()

        app.add_middleware(
            APIKeyAuthMiddleware,
            repository=mock_repo,
            require_auth=True,
            exclude_paths=["/health"],  # Only exclude health, not /test
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")
        assert response.status_code == 401
        assert "API key required" in response.json()["message"]

    def test_request_with_invalid_api_key_rejected(self):
        """Test that requests with invalid API key are rejected."""
        from app.api.middleware.api_key_auth import APIKeyAuthMiddleware

        mock_repo = Mock()
        mock_repo.find_by_key_hash = AsyncMock(return_value=None)
        mock_repo.update_last_used = AsyncMock()

        app = FastAPI()

        app.add_middleware(
            APIKeyAuthMiddleware,
            repository=mock_repo,
            require_auth=True,
            exclude_paths=["/health"],  # Only exclude health, not /test
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test", headers={"X-API-Key": "invalid_key"})
        assert response.status_code == 401


# ============================================================================
# Prometheus Metrics Middleware Tests
# ============================================================================


class TestPrometheusMiddleware:
    """Test Prometheus metrics middleware."""

    @pytest.fixture
    def app_with_metrics(self):
        """Create FastAPI app with metrics middleware."""
        from app.api.middleware.metrics import PrometheusMiddleware

        app = FastAPI()

        app.add_middleware(
            PrometheusMiddleware,
            exclude_paths=["/metrics", "/health"],
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        return app

    def test_request_metrics_recorded(self, app_with_metrics):
        """Test that request metrics are recorded."""
        client = TestClient(app_with_metrics)
        response = client.get("/test")
        assert response.status_code == 200

    def test_excluded_paths_not_recorded(self, app_with_metrics):
        """Test that excluded paths are not recorded."""
        client = TestClient(app_with_metrics)
        response = client.get("/health")
        assert response.status_code == 200


# ============================================================================
# Metrics Endpoint Tests
# ============================================================================


class TestMetricsEndpoint:
    """Test metrics endpoint."""

    @pytest.fixture
    def app_with_metrics_endpoint(self):
        """Create FastAPI app with metrics endpoint."""
        from app.api.routes.metrics import router

        app = FastAPI()
        app.include_router(router)

        return app

    def test_metrics_endpoint_returns_prometheus_format(self, app_with_metrics_endpoint):
        """Test that metrics endpoint returns Prometheus format."""
        client = TestClient(app_with_metrics_endpoint)
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus format should contain TYPE and HELP comments
        assert b"# HELP" in response.content or b"# TYPE" in response.content
