"""API middleware."""

from app.api.middleware.error_handler import setup_exception_handlers
from app.api.middleware.rate_limit import RateLimitMiddleware, create_rate_limit_middleware
from app.api.middleware.api_key_auth import (
    APIKeyAuthMiddleware,
    get_api_key_context,
    require_scope,
    RequireAPIKey,
)

__all__ = [
    "setup_exception_handlers",
    "RateLimitMiddleware",
    "create_rate_limit_middleware",
    "APIKeyAuthMiddleware",
    "get_api_key_context",
    "require_scope",
    "RequireAPIKey",
]
