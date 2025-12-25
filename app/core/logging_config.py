"""Comprehensive logging configuration with structured logging and correlation IDs.

This module provides:
- Structured JSON logging for production
- Request correlation IDs for distributed tracing
- Security event logging
- Performance monitoring
- Error tracking
"""

import logging
import logging.config
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import json
import contextvars

from app.core.config import settings

# Context variable for request correlation ID
request_id_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'request_id', default=None
)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id to log record if available."""
        record.request_id = request_id_context.get() or "N/A"
        return True


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, 'request_id', 'N/A'),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'tenant_id'):
            log_data["tenant_id"] = record.tenant_id
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, 'event_type'):
            log_data["event_type"] = record.event_type

        return json.dumps(log_data)


class SecurityEventLogger:
    """Dedicated logger for security events."""

    def __init__(self):
        self.logger = logging.getLogger("security")

    def log_authentication_attempt(
        self,
        user_id: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log authentication attempt."""
        extra = {
            "event_type": "authentication_attempt",
            "user_id": user_id,
            "success": success,
            "ip_address": ip_address or "unknown",
            "user_agent": user_agent or "unknown",
        }
        
        if success:
            self.logger.info("Authentication successful", extra=extra)
        else:
            self.logger.warning("Authentication failed", extra=extra)

    def log_authorization_failure(
        self,
        user_id: str,
        resource: str,
        action: str,
    ):
        """Log authorization failure."""
        self.logger.warning(
            "Authorization denied",
            extra={
                "event_type": "authorization_failure",
                "user_id": user_id,
                "resource": resource,
                "action": action,
            }
        )

    def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ):
        """Log sensitive data access."""
        self.logger.info(
            "Data access",
            extra={
                "event_type": "data_access",
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
            }
        )

    def log_suspicious_activity(
        self,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log suspicious activity."""
        extra = {
            "event_type": "suspicious_activity",
            "description": description,
        }
        if user_id:
            extra["user_id"] = user_id
        if ip_address:
            extra["ip_address"] = ip_address
        if details:
            extra.update(details)

        self.logger.warning("Suspicious activity detected", extra=extra)


# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": CorrelationIdFilter,
        },
    },
    "formatters": {
        "default": {
            "format": "[%(asctime)s] [%(request_id)s] %(levelname)s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "structured": {
            "()": StructuredFormatter,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "formatter": "structured" if settings.ENVIRONMENT == "production" else "default",
            "stream": sys.stdout,
            "filters": ["correlation_id"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "structured",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "filters": ["correlation_id"],
        },
        "security": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "structured",
            "filename": "logs/security.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "filters": ["correlation_id"],
        },
        "error": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "structured",
            "filename": "logs/error.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "filters": ["correlation_id"],
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file", "error"],
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "propagate": False,
        },
        "security": {
            "handlers": ["security", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "fastapi": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


def setup_logging():
    """Setup logging configuration."""
    import os
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    logging.config.dictConfig(LOGGING_CONFIG)
    
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized: environment={settings.ENVIRONMENT}, "
        f"debug={settings.DEBUG}"
    )


# Global security event logger instance
security_logger = SecurityEventLogger()
