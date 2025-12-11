"""Security middleware for HTTP security headers and protection."""

import logging
import re
from typing import Callable, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Implements OWASP security header recommendations:
    - Content-Security-Policy
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        frame_options: str = "DENY",
        content_type_options: bool = True,
        xss_protection: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: Optional[str] = None,
    ):
        """Initialize security headers middleware.

        Args:
            app: FastAPI/Starlette application
            enable_hsts: Enable HTTP Strict Transport Security
            hsts_max_age: HSTS max-age in seconds
            frame_options: X-Frame-Options value (DENY, SAMEORIGIN)
            content_type_options: Enable X-Content-Type-Options: nosniff
            xss_protection: Enable X-XSS-Protection
            referrer_policy: Referrer-Policy header value
            permissions_policy: Permissions-Policy header value
        """
        super().__init__(app)
        self._enable_hsts = enable_hsts
        self._hsts_max_age = hsts_max_age
        self._frame_options = frame_options
        self._content_type_options = content_type_options
        self._xss_protection = xss_protection
        self._referrer_policy = referrer_policy
        self._permissions_policy = permissions_policy or (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        logger.info("SecurityHeadersMiddleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # X-Content-Type-Options
        if self._content_type_options:
            response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options
        response.headers["X-Frame-Options"] = self._frame_options

        # X-XSS-Protection (legacy but still useful)
        if self._xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy
        response.headers["Referrer-Policy"] = self._referrer_policy

        # Permissions-Policy
        response.headers["Permissions-Policy"] = self._permissions_policy

        # Strict-Transport-Security (only for HTTPS)
        if self._enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._hsts_max_age}; includeSubDomains"
            )

        # Content-Security-Policy (restrictive for API)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'none'"
        )

        # Remove server header if present
        if "server" in response.headers:
            del response.headers["server"]

        return response


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware to sanitize and validate input data.

    Protects against:
    - SQL injection patterns
    - XSS patterns
    - Path traversal
    - Command injection
    """

    # Dangerous patterns to detect
    SQL_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)",
        r"(--|;|/\*|\*/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*=\s*\d+)",
    ]

    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e[/\\]",
    ]

    def __init__(
        self,
        app,
        check_sql: bool = True,
        check_xss: bool = True,
        check_path_traversal: bool = True,
        exclude_paths: Optional[List[str]] = None,
    ):
        """Initialize input sanitization middleware.

        Args:
            app: FastAPI/Starlette application
            check_sql: Check for SQL injection patterns
            check_xss: Check for XSS patterns
            check_path_traversal: Check for path traversal
            exclude_paths: Paths to exclude from checking
        """
        super().__init__(app)
        self._check_sql = check_sql
        self._check_xss = check_xss
        self._check_path_traversal = check_path_traversal
        self._exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json"]

        # Compile patterns
        self._sql_regex = [re.compile(p, re.IGNORECASE) for p in self.SQL_PATTERNS]
        self._xss_regex = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]
        self._path_regex = [
            re.compile(p, re.IGNORECASE) for p in self.PATH_TRAVERSAL_PATTERNS
        ]

        logger.info("InputSanitizationMiddleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request for malicious patterns.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response or 400 if malicious input detected
        """
        from fastapi.responses import JSONResponse

        path = request.url.path

        # Skip excluded paths
        if any(path.startswith(excluded) for excluded in self._exclude_paths):
            return await call_next(request)

        # Check query parameters
        query_string = str(request.url.query)
        if query_string:
            threat = self._detect_threat(query_string)
            if threat:
                logger.warning(
                    f"Blocked malicious query parameter: {threat}",
                    extra={"path": path, "threat_type": threat},
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error_code": "INVALID_INPUT",
                        "message": "Request contains invalid characters",
                    },
                )

        # Check path
        if self._check_path_traversal:
            threat = self._detect_path_traversal(path)
            if threat:
                logger.warning(
                    f"Blocked path traversal attempt: {path}",
                    extra={"path": path, "threat_type": "path_traversal"},
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error_code": "INVALID_PATH",
                        "message": "Invalid path",
                    },
                )

        return await call_next(request)

    def _detect_threat(self, value: str) -> Optional[str]:
        """Detect malicious patterns in value.

        Args:
            value: String to check

        Returns:
            Threat type if detected, None otherwise
        """
        if self._check_sql:
            for pattern in self._sql_regex:
                if pattern.search(value):
                    return "sql_injection"

        if self._check_xss:
            for pattern in self._xss_regex:
                if pattern.search(value):
                    return "xss"

        return None

    def _detect_path_traversal(self, path: str) -> bool:
        """Check for path traversal patterns.

        Args:
            path: URL path

        Returns:
            True if path traversal detected
        """
        for pattern in self._path_regex:
            if pattern.search(path):
                return True
        return False


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size.

    Prevents denial-of-service through large payloads.
    """

    def __init__(
        self,
        app,
        max_content_length: int = 50 * 1024 * 1024,  # 50MB default
    ):
        """Initialize request size limit middleware.

        Args:
            app: FastAPI/Starlette application
            max_content_length: Maximum content length in bytes
        """
        super().__init__(app)
        self._max_content_length = max_content_length
        logger.info(
            f"RequestSizeLimitMiddleware initialized (max={max_content_length} bytes)"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response or 413 if too large
        """
        from fastapi.responses import JSONResponse

        content_length = request.headers.get("content-length")

        if content_length:
            try:
                length = int(content_length)
                if length > self._max_content_length:
                    logger.warning(
                        f"Request too large: {length} bytes (max: {self._max_content_length})"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error_code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds maximum size of {self._max_content_length} bytes",
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)
