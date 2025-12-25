"""Correlation ID middleware for request tracking.

Adds a unique correlation ID to each request for distributed tracing and logging.
"""

import logging
import re
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import request_id_context

logger = logging.getLogger(__name__)

# Regex for validating correlation IDs (alphanumeric and hyphens only, max 64 chars)
# Prevents log injection, XSS, path traversal, and DoS attacks
CORRELATION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9-]{1,64}$')


def validate_correlation_id(value: Optional[str]) -> Optional[str]:
    """Validate correlation ID format for security.

    Args:
        value: Client-provided correlation ID

    Returns:
        Validated correlation ID or None if invalid

    Security:
        - Prevents log injection attacks
        - Prevents XSS in log viewers
        - Prevents path traversal if used in file paths
        - Prevents DoS with extremely long IDs
    """
    if not value:
        return None

    # Check length and format
    if len(value) > 64 or not CORRELATION_ID_PATTERN.match(value):
        logger.warning(
            f"Invalid correlation ID rejected: {value[:20]}... "
            f"(length={len(value)})"
        )
        return None

    return value


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to requests.
    
    Features:
    - Generates unique correlation ID for each request
    - Accepts existing correlation ID from X-Request-ID header
    - Adds correlation ID to response headers
    - Sets correlation ID in context for logging
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with correlation ID.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response with correlation ID header
        """
        # Get and validate correlation ID from client, or generate new one
        client_id = request.headers.get("X-Request-ID")
        validated_id = validate_correlation_id(client_id)

        correlation_id = validated_id if validated_id else str(uuid.uuid4())

        # Set in context for logging
        request_id_context.set(correlation_id)
        
        # Add to request state
        request.state.request_id = correlation_id
        
        # Log request
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Add correlation ID to response headers
            response.headers["X-Request-ID"] = correlation_id
            
            # Log response
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": correlation_id,
                    "status_code": response.status_code,
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Request failed: {str(e)}",
                extra={"request_id": correlation_id},
                exc_info=True
            )
            raise
