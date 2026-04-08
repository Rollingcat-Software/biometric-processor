"""Simple API key authentication middleware.

Validates requests against a single shared API key.
Used in production to restrict biometric API access to
identity-core-api and other authorized services.
"""

import logging
from typing import Callable, List, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SimpleAPIKeyMiddleware(BaseHTTPMiddleware):
    """Simple shared-secret API key middleware.

    Requires X-API-Key header matching the configured secret
    for all /api/v1/* routes (except excluded paths).
    Static files (/, /_next/*) and health endpoints are always allowed.
    """

    def __init__(
        self,
        app,
        api_key: str,
        header_name: str = "X-API-Key",
        exclude_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self._api_key = api_key
        self._header_name = header_name
        self._exclude_paths = exclude_paths or []

        if not api_key:
            logger.warning(
                "SimpleAPIKeyMiddleware: API_KEY_SECRET is empty! "
                "All API requests will be rejected."
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip excluded paths (health, docs, static files)
        if any(path.startswith(excluded) for excluded in self._exclude_paths):
            return await call_next(request)

        # Only enforce on /api/* routes
        if not path.startswith("/api/"):
            return await call_next(request)

        # Validate API key
        provided_key = request.headers.get(self._header_name)

        if not provided_key:
            logger.warning(f"Missing API key for {request.method} {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error_code": "UNAUTHORIZED",
                    "message": "API key required. Provide X-API-Key header.",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if provided_key != self._api_key:
            logger.warning(
                f"Invalid API key for {request.method} {path} "
                f"(prefix: {provided_key[:8]}...)"
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error_code": "UNAUTHORIZED",
                    "message": "Invalid API key.",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return await call_next(request)
