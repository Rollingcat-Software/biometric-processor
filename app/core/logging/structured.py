"""Structured logging configuration using structlog."""

import logging
import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.types import Processor

# Context variable for request-scoped logging context
_log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


class LogContext:
    """Context manager for adding logging context.

    Usage:
        with LogContext(request_id="abc123", tenant_id="tenant1"):
            logger.info("Processing request")
            # All logs within this block will include request_id and tenant_id
    """

    def __init__(self, **kwargs: Any):
        """Initialize with context values.

        Args:
            **kwargs: Key-value pairs to add to logging context
        """
        self._context = kwargs
        self._previous_context: Optional[Dict[str, Any]] = None

    def __enter__(self) -> "LogContext":
        """Enter context and add values."""
        current = _log_context.get()
        self._previous_context = current.copy()
        new_context = {**current, **self._context}
        _log_context.set(new_context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and restore previous values."""
        if self._previous_context is not None:
            _log_context.set(self._previous_context)


def add_context(**kwargs: Any) -> None:
    """Add values to the current logging context.

    Args:
        **kwargs: Key-value pairs to add
    """
    current = _log_context.get()
    _log_context.set({**current, **kwargs})


def clear_context() -> None:
    """Clear all values from the current logging context."""
    _log_context.set({})


def get_context() -> Dict[str, Any]:
    """Get the current logging context.

    Returns:
        Current context dictionary
    """
    return _log_context.get()


def add_context_processor(
    logger: logging.Logger,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Structlog processor to add context variables.

    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Event dictionary

    Returns:
        Modified event dictionary with context
    """
    context = get_context()
    # Add context at the beginning, event dict values take precedence
    return {**context, **event_dict}


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "biometric-processor",
    version: str = "1.0.0",
) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "text")
        service_name: Service name for logs
        version: Service version for logs
    """
    # Determine if we should use colored output (text format only)
    use_colors = log_format == "text" and sys.stderr.isatty()

    # Common processors for all formats
    common_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_context_processor,
    ]

    # Add static fields
    def add_service_info(
        logger: logging.Logger,
        method_name: str,
        event_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add service information to all log events."""
        event_dict["service"] = service_name
        event_dict["version"] = version
        return event_dict

    common_processors.append(add_service_info)

    # Format-specific processors
    if log_format == "json":
        # JSON format for production
        processors = common_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Text format for development
        processors = common_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=use_colors),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Set level for third-party loggers
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
        logging.getLogger(logger_name).setLevel(getattr(logging, log_level.upper()))


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (optional)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class RequestLoggingMiddleware:
    """Middleware for adding request context to logs.

    Automatically adds request_id, method, path, and other
    request metadata to all logs within the request context.
    """

    def __init__(self, app):
        """Initialize middleware.

        Args:
            app: ASGI application
        """
        self.app = app
        self.logger = get_logger("http")

    async def __call__(self, scope, receive, send):
        """Process request and add logging context.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time
        import uuid

        # Generate request ID
        request_id = scope.get("headers", {})
        request_id_header = None
        for header_name, header_value in scope.get("headers", []):
            if header_name.decode().lower() == "x-request-id":
                request_id_header = header_value.decode()
                break

        request_id = request_id_header or str(uuid.uuid4())

        # Extract request info
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        client = scope.get("client", ("unknown", 0))
        client_ip = client[0] if client else "unknown"

        # Add context for this request
        with LogContext(
            request_id=request_id,
            method=method,
            path=path,
            client_ip=client_ip,
        ):
            start_time = time.time()

            # Track response status
            status_code = 500

            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message.get("status", 500)
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as e:
                self.logger.exception(
                    "Request failed with exception",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
            finally:
                duration = time.time() - start_time
                self.logger.info(
                    "Request completed",
                    status_code=status_code,
                    duration_ms=round(duration * 1000, 2),
                )
