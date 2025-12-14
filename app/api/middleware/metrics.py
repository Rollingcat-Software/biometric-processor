"""Prometheus metrics middleware for request tracking."""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import get_metrics

logger = logging.getLogger(__name__)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting Prometheus metrics on HTTP requests.

    Tracks:
    - Request count by method, endpoint, and status code
    - Request latency histogram
    - Active requests gauge
    """

    def __init__(self, app, exclude_paths: list = None):
        """Initialize the metrics middleware.

        Args:
            app: FastAPI/Starlette application
            exclude_paths: Paths to exclude from metrics (e.g., /health, /metrics)
        """
        super().__init__(app)
        self._exclude_paths = exclude_paths or ["/metrics", "/health"]
        self._metrics = get_metrics()
        logger.info("PrometheusMiddleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics.

        Args:
            request: HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response
        """
        path = request.url.path
        method = request.method

        # Skip excluded paths
        if any(path.startswith(excluded) for excluded in self._exclude_paths):
            return await call_next(request)

        # Normalize path for metrics (remove IDs, etc.)
        normalized_path = self._normalize_path(path)

        # Track request
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

        except Exception as e:
            # Record error
            self._metrics.record_error(
                error_type=type(e).__name__,
                endpoint=normalized_path,
            )
            raise

        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            self._metrics.record_request(
                method=method,
                endpoint=normalized_path,
                status_code=status_code if "status_code" in dir() else 500,
                duration=duration,
            )

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics grouping.

        Replaces dynamic path segments (UUIDs, IDs) with placeholders
        to prevent high cardinality in metrics.

        Args:
            path: Original request path

        Returns:
            Normalized path
        """
        import re

        # Remove API version prefix for cleaner metrics
        normalized = path

        # Replace UUIDs with placeholder
        uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        normalized = re.sub(uuid_pattern, "{id}", normalized)

        # Replace numeric IDs with placeholder
        # Match /resource/123 but not /v1 or /api
        normalized = re.sub(r"/(\d{2,})(?=/|$)", "/{id}", normalized)

        return normalized
