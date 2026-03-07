"""Rate limiting middleware for API request throttling."""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.domain.interfaces.rate_limit_storage import IRateLimitStorage, RateLimitInfo

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit_info: RateLimitInfo):
        self.limit_info = limit_info
        super().__init__(f"Rate limit exceeded. Retry after {limit_info.reset_at}")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with sliding window algorithm.

    Applies rate limiting based on:
    - API key (if provided in X-API-Key header)
    - Client IP address (fallback)
    - Tenant ID (if provided in X-Tenant-ID header)

    Adds rate limit headers to responses:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Remaining requests in window
    - X-RateLimit-Reset: Unix timestamp when limit resets

    When rate limit is exceeded, returns HTTP 429 with Retry-After header.
    """

    def __init__(
        self,
        app,
        storage: IRateLimitStorage,
        default_limit: int = 60,
        window_seconds: int = 60,
        exclude_paths: Optional[list] = None,
    ):
        """Initialize rate limit middleware.

        Args:
            app: FastAPI/Starlette application
            storage: Rate limit storage backend
            default_limit: Default requests per window
            window_seconds: Time window in seconds
            exclude_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self._storage = storage
        self._default_limit = default_limit
        self._window_seconds = window_seconds
        self._exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]
        self._tier_limits = {
            "free": settings.RATE_LIMIT_DEFAULT // 2,
            "standard": settings.RATE_LIMIT_DEFAULT,
            "premium": settings.RATE_LIMIT_PREMIUM,
            "unlimited": 999999,
        }
        logger.info(
            f"RateLimitMiddleware initialized: {default_limit} requests/{window_seconds}s"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply rate limiting.

        Args:
            request: HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response with rate limit headers
        """
        # Skip rate limiting if disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for authenticated service-to-service calls
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return await call_next(request)

        # Skip excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self._exclude_paths):
            return await call_next(request)

        # Get rate limit key
        key = self._get_key(request)

        # Get limit based on tier
        limit = await self._get_limit_for_key(key)

        try:
            # Check and increment rate limit
            limit_info = await self._storage.increment(
                key=key,
                limit=limit,
                window_seconds=self._window_seconds,
            )

            # Check if limit exceeded
            if limit_info.remaining < 0:
                return self._create_rate_limit_response(limit_info)

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            self._add_rate_limit_headers(response, limit_info)

            return response

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # On error, allow request through (fail open for availability)
            return await call_next(request)

    def _get_key(self, request: Request) -> str:
        """Extract rate limit key from request.

        Priority:
        1. X-API-Key header
        2. X-Tenant-ID header
        3. Client IP address

        Args:
            request: HTTP request

        Returns:
            Rate limit key string
        """
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"

        # Check for tenant ID
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return f"tenant:{tenant_id}"

        # Fall back to client IP
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request.

        Handles X-Forwarded-For header for proxied requests.

        Args:
            request: HTTP request

        Returns:
            Client IP address string
        """
        # Check X-Forwarded-For header (for proxied requests)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _get_limit_for_key(self, key: str) -> int:
        """Get rate limit for a key based on tier.

        Args:
            key: Rate limit key

        Returns:
            Rate limit for the key
        """
        # Get existing rate limit info to check tier
        info = await self._storage.get(key)
        if info and info.tier:
            return self._tier_limits.get(info.tier, self._default_limit)

        return self._default_limit

    def _add_rate_limit_headers(
        self, response: Response, limit_info: RateLimitInfo
    ) -> None:
        """Add rate limit headers to response.

        Args:
            response: HTTP response
            limit_info: Current rate limit information
        """
        response.headers["X-RateLimit-Limit"] = str(limit_info.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit_info.remaining))
        response.headers["X-RateLimit-Reset"] = str(limit_info.reset_at)
        response.headers["X-RateLimit-Tier"] = limit_info.tier

    def _create_rate_limit_response(self, limit_info: RateLimitInfo) -> JSONResponse:
        """Create HTTP 429 response for rate limit exceeded.

        Args:
            limit_info: Rate limit information

        Returns:
            JSONResponse with 429 status
        """
        retry_after = max(0, limit_info.reset_at - int(time.time()))

        logger.warning(
            f"Rate limit exceeded for tier {limit_info.tier}. "
            f"Retry after {retry_after} seconds."
        )

        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please retry later.",
                "retry_after_seconds": retry_after,
                "tier": limit_info.tier,
            },
        )

        # Add headers
        response.headers["Retry-After"] = str(retry_after)
        self._add_rate_limit_headers(response, limit_info)

        return response


def create_rate_limit_middleware(
    storage: IRateLimitStorage,
    default_limit: Optional[int] = None,
    window_seconds: int = 60,
) -> RateLimitMiddleware:
    """Factory function to create rate limit middleware.

    Args:
        storage: Rate limit storage backend
        default_limit: Default requests per window (uses config if not specified)
        window_seconds: Time window in seconds

    Returns:
        Configured RateLimitMiddleware instance
    """
    limit = default_limit or settings.RATE_LIMIT_PER_MINUTE

    return RateLimitMiddleware(
        app=None,  # Will be set by FastAPI
        storage=storage,
        default_limit=limit,
        window_seconds=window_seconds,
    )
