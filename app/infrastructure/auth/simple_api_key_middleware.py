"""Simple API key authentication middleware (pure ASGI).

Validates requests against a single shared API key.
Used in production to restrict biometric API access to
identity-core-api and other authorized services.
"""

import json
import logging
from typing import List, Optional

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class SimpleAPIKeyMiddleware:
    """Pure ASGI middleware for API key validation.

    Requires X-API-Key header matching the configured secret
    for all /api/* routes (except excluded paths).
    """

    def __init__(
        self,
        app: ASGIApp,
        api_key: str,
        header_name: str = "X-API-Key",
        exclude_paths: Optional[List[str]] = None,
    ):
        self.app = app
        self._api_key = api_key
        self._header_name = header_name.lower().encode()
        self._exclude_paths = exclude_paths or []

        if not api_key:
            logger.warning(
                "SimpleAPIKeyMiddleware: API_KEY_SECRET is empty! "
                "All API requests will be rejected."
            )
        logger.info("SimpleAPIKeyMiddleware initialized")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip non-API routes and excluded paths
        if not path.startswith("/api/") or any(
            path.startswith(excluded) for excluded in self._exclude_paths
        ):
            await self.app(scope, receive, send)
            return

        # Extract API key from headers
        headers = dict(scope.get("headers", []))
        provided_key = headers.get(self._header_name, b"").decode()

        if not provided_key:
            logger.warning(f"Missing API key for {scope.get('method', '?')} {path}")
            await self._send_401(send, "API key required. Provide X-API-Key header.")
            return

        if provided_key != self._api_key:
            logger.warning(
                f"Invalid API key for {scope.get('method', '?')} {path} "
                f"(prefix: {provided_key[:8]}...)"
            )
            await self._send_401(send, "Invalid API key.")
            return

        # Valid key — proceed
        await self.app(scope, receive, send)

    async def _send_401(self, send: Send, message: str) -> None:
        body = json.dumps({
            "error_code": "UNAUTHORIZED",
            "message": message,
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"www-authenticate", b"ApiKey"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
