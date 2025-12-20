"""OpenTelemetry tracing middleware for FastAPI.

Provides request-level tracing with automatic span creation and attribute extraction.
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.tracing.instrumentation import (
    OTEL_AVAILABLE,
    SpanAttributes,
    SpanContext,
    add_span_attributes,
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for request-level OpenTelemetry tracing.

    Adds spans for each HTTP request with relevant attributes.
    """

    # Paths to exclude from tracing
    EXCLUDED_PATHS = {"/health", "/metrics", "/api/v1/health", "/favicon.ico"}

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request with tracing.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            HTTP response.
        """
        # Skip tracing for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Extract span name from route
        span_name = f"{request.method} {request.url.path}"

        # Start timing
        start_time = time.perf_counter()

        # Create attributes
        attributes = {
            "http.method": request.method,
            "http.url": str(request.url),
            "http.route": request.url.path,
            "http.host": request.url.hostname,
            "http.scheme": request.url.scheme,
            "http.user_agent": request.headers.get("user-agent", ""),
        }

        # Extract user/tenant from headers or auth
        if "x-user-id" in request.headers:
            attributes[SpanAttributes.USER_ID] = request.headers["x-user-id"]
        if "x-tenant-id" in request.headers:
            attributes[SpanAttributes.TENANT_ID] = request.headers["x-tenant-id"]

        # Extract trace context from headers
        if "x-request-id" in request.headers:
            attributes["http.request_id"] = request.headers["x-request-id"]

        try:
            if OTEL_AVAILABLE:
                from opentelemetry.trace import SpanKind

                with SpanContext(
                    span_name,
                    kind=SpanKind.SERVER,
                    attributes=attributes,
                ) as span:
                    response = await call_next(request)

                    # Add response attributes
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute("http.response_time_ms", round(duration_ms, 2))

                    # Add content length if available
                    if "content-length" in response.headers:
                        span.set_attribute(
                            "http.response_content_length",
                            int(response.headers["content-length"]),
                        )

                    return response
            else:
                return await call_next(request)

        except Exception as e:
            # Record exception if tracing is available
            if OTEL_AVAILABLE:
                from app.core.tracing.instrumentation import record_exception

                record_exception(e)
            raise


class BiometricTracingMiddleware(BaseHTTPMiddleware):
    """Specialized tracing middleware for biometric operations.

    Extracts biometric-specific attributes from requests and responses.
    """

    # Biometric endpoint patterns
    BIOMETRIC_ENDPOINTS = {
        "/api/v1/enroll": "biometric.enroll",
        "/api/v1/verify": "biometric.verify",
        "/api/v1/search": "biometric.search",
        "/api/v1/liveness": "biometric.liveness",
    }

    PROCTORING_ENDPOINTS = {
        "/api/v1/proctor/sessions": "proctoring.session",
        "/api/v1/proctor/sessions/{id}/frames": "proctoring.frame",
    }

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process biometric request with specialized tracing.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            HTTP response.
        """
        path = request.url.path

        # Check if this is a biometric or proctoring endpoint
        operation_name = None
        for endpoint, name in self.BIOMETRIC_ENDPOINTS.items():
            if path.startswith(endpoint):
                operation_name = name
                break

        if not operation_name:
            for endpoint, name in self.PROCTORING_ENDPOINTS.items():
                if endpoint.split("{")[0] in path:
                    operation_name = name
                    break

        if not operation_name:
            return await call_next(request)

        # Add biometric-specific attributes
        attributes = {
            "biometric.operation": operation_name,
        }

        # Try to extract content type for image operations
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            attributes[SpanAttributes.IMAGE_FORMAT] = "multipart"
        elif "application/json" in content_type:
            attributes[SpanAttributes.IMAGE_FORMAT] = "base64"

        add_span_attributes(attributes)

        return await call_next(request)
