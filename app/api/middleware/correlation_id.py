"""Correlation ID middleware for request tracking.

Adds a unique correlation ID to each request for distributed tracing and logging.
"""

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import request_id_context

logger = logging.getLogger(__name__)


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
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
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
