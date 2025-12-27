"""Security headers middleware for hardening HTTP responses."""

import logging
from typing import Callable, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses.

    Implements security best practices:
    - Prevent clickjacking (X-Frame-Options)
    - Prevent MIME sniffing (X-Content-Type-Options)
    - XSS protection (X-XSS-Protection)
    - Referrer policy (Referrer-Policy)
    - Content Security Policy (CSP)
    - HTTP Strict Transport Security (HSTS)
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        frame_options: str = "DENY",
        content_type_options: str = "nosniff",
        xss_protection: str = "1; mode=block",
        referrer_policy: str = "strict-origin-when-cross-origin",
        csp_policy: Optional[str] = None,
        exclude_paths: Optional[List[str]] = None,
    ):
        """Initialize security headers middleware.

        Args:
            app: FastAPI/Starlette application
            enable_hsts: Enable HSTS header (recommended for production)
            hsts_max_age: HSTS max-age in seconds
            hsts_include_subdomains: Include subdomains in HSTS
            frame_options: X-Frame-Options value
            content_type_options: X-Content-Type-Options value
            xss_protection: X-XSS-Protection value
            referrer_policy: Referrer-Policy value
            csp_policy: Content-Security-Policy value (None for default)
            exclude_paths: Paths to exclude from security headers
        """
        super().__init__(app)

        self._enable_hsts = enable_hsts
        self._hsts_max_age = hsts_max_age
        self._hsts_include_subdomains = hsts_include_subdomains
        self._frame_options = frame_options
        self._content_type_options = content_type_options
        self._xss_protection = xss_protection
        self._referrer_policy = referrer_policy
        self._exclude_paths = exclude_paths or []

        # Default CSP policy (Next.js-compatible)
        self._csp_policy = csp_policy or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Next.js requires unsafe-inline/eval
            "style-src 'self' 'unsafe-inline'; "  # CSS-in-JS requires unsafe-inline
            "img-src 'self' data: blob: https:; "  # Allow data URIs, blobs, and HTTPS images
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "  # WebSocket support for real-time features
            "frame-ancestors 'self'; "  # Equivalent to X-Frame-Options
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"  # Upgrade HTTP to HTTPS
        )

        logger.info("SecurityHeadersMiddleware initialized")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and add security headers to response.

        Args:
            request: HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response with security headers
        """
        # Check if path should be excluded
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self._exclude_paths):
            return await call_next(request)

        # Process request
        response = await call_next(request)

        # Add security headers
        self._add_security_headers(request, response)

        return response

    def _add_security_headers(self, request: Request, response: Response) -> None:
        """Add security headers to response.

        Args:
            request: HTTP request (for context)
            response: HTTP response to modify
        """
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = self._frame_options

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = self._content_type_options

        # XSS protection (legacy, but still useful for older browsers)
        response.headers["X-XSS-Protection"] = self._xss_protection

        # Referrer policy
        response.headers["Referrer-Policy"] = self._referrer_policy

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self._csp_policy

        # Permissions Policy (modern replacement for Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS - only for HTTPS or non-localhost
        if self._enable_hsts:
            hostname = request.url.hostname or ""
            if hostname not in ("localhost", "127.0.0.1", "0.0.0.0"):
                hsts_value = f"max-age={self._hsts_max_age}"
                if self._hsts_include_subdomains:
                    hsts_value += "; includeSubDomains"
                response.headers["Strict-Transport-Security"] = hsts_value

        # Additional headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Cache control for sensitive endpoints
        if "/api/" in request.url.path:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    def __init__(
        self,
        app,
        max_body_size: int = 50 * 1024 * 1024,  # 50MB default
    ):
        """Initialize request size limit middleware.

        Args:
            app: FastAPI/Starlette application
            max_body_size: Maximum allowed body size in bytes
        """
        super().__init__(app)
        self._max_body_size = max_body_size

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Check request size and process.

        Args:
            request: HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response
        """
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self._max_body_size:
                    return Response(
                        content='{"detail": "Request body too large"}',
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                pass

        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware for security audit logging."""

    def __init__(
        self,
        app,
        log_headers: bool = False,
        sensitive_paths: Optional[List[str]] = None,
    ):
        """Initialize audit log middleware.

        Args:
            app: FastAPI/Starlette application
            log_headers: Whether to log request headers
            sensitive_paths: Paths that require extra logging
        """
        super().__init__(app)
        self._log_headers = log_headers
        self._sensitive_paths = sensitive_paths or ["/api/v1/proctoring"]
        self._logger = logging.getLogger("security.audit")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Log request and response for audit trail.

        Args:
            request: HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response
        """
        import time
        import uuid

        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        tenant_id = request.headers.get("X-Tenant-ID", "unknown")

        # Check if sensitive path
        is_sensitive = any(
            request.url.path.startswith(p) for p in self._sensitive_paths
        )

        # Log request
        log_data = {
            "event": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "tenant_id": tenant_id,
            "user_agent": user_agent,
            "sensitive": is_sensitive,
        }

        if self._log_headers and is_sensitive:
            # Log safe headers only
            safe_headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower()
                not in ("authorization", "x-api-key", "cookie", "set-cookie")
            }
            log_data["headers"] = safe_headers

        start_time = time.time()

        try:
            response = await call_next(request)

            # Log response
            duration_ms = (time.time() - start_time) * 1000
            log_data.update(
                {
                    "event": "http_response",
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            if is_sensitive:
                self._logger.info(
                    f"AUDIT: {request.method} {request.url.path} "
                    f"-> {response.status_code} ({duration_ms:.1f}ms)"
                )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._logger.error(
                f"AUDIT ERROR: {request.method} {request.url.path} "
                f"-> {type(e).__name__}: {e} ({duration_ms:.1f}ms)"
            )
            raise
