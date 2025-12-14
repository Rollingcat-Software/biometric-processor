"""OpenTelemetry tracing configuration."""

from app.core.tracing.config import TracingConfig, setup_tracing
from app.core.tracing.instrumentation import (
    trace_async,
    trace_sync,
    get_current_span,
    add_span_attributes,
    record_exception,
)

__all__ = [
    "TracingConfig",
    "setup_tracing",
    "trace_async",
    "trace_sync",
    "get_current_span",
    "add_span_attributes",
    "record_exception",
]
