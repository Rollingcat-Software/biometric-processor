"""OpenTelemetry instrumentation utilities.

Provides decorators and helpers for adding tracing to functions.
"""

import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Try to import OpenTelemetry, provide stubs if not available
try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode, SpanKind
    from opentelemetry.trace.propagation import set_span_in_context

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    Span = None
    Status = None
    StatusCode = None
    SpanKind = None


def get_tracer(name: str = "biometric-processor"):
    """Get a tracer instance.

    Args:
        name: Tracer name (usually module name).

    Returns:
        Tracer instance or None if OpenTelemetry not available.
    """
    if not OTEL_AVAILABLE:
        return None
    return trace.get_tracer(name)


def get_current_span() -> Optional[Any]:
    """Get the current active span.

    Returns:
        Current span or None if no active span or OTEL not available.
    """
    if not OTEL_AVAILABLE:
        return None
    return trace.get_current_span()


def add_span_attributes(attributes: Dict[str, Any]) -> None:
    """Add attributes to the current span.

    Args:
        attributes: Dictionary of attribute key-value pairs.
    """
    span = get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            # Convert value to string if not a primitive type
            if not isinstance(value, (str, int, float, bool)):
                value = str(value)
            span.set_attribute(key, value)


def record_exception(
    exception: Exception,
    attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an exception on the current span.

    Args:
        exception: The exception to record.
        attributes: Optional additional attributes.
    """
    span = get_current_span()
    if span and span.is_recording():
        span.record_exception(exception, attributes=attributes)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


def trace_sync(
    name: Optional[str] = None,
    kind: Optional[Any] = None,
    attributes: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """Decorator to trace synchronous functions.

    Args:
        name: Span name. Defaults to function name.
        kind: Span kind (INTERNAL, SERVER, CLIENT, etc.).
        attributes: Static attributes to add to span.

    Returns:
        Decorated function.

    Example:
        @trace_sync(name="process_image", attributes={"component": "ml"})
        def process_image(image_data):
            ...
    """

    def decorator(func: F) -> F:
        if not OTEL_AVAILABLE:
            return func

        span_name = name or func.__name__
        span_kind = kind or SpanKind.INTERNAL
        tracer = get_tracer(func.__module__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                span_name,
                kind=span_kind,
                attributes=attributes,
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


def trace_async(
    name: Optional[str] = None,
    kind: Optional[Any] = None,
    attributes: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """Decorator to trace asynchronous functions.

    Args:
        name: Span name. Defaults to function name.
        kind: Span kind (INTERNAL, SERVER, CLIENT, etc.).
        attributes: Static attributes to add to span.

    Returns:
        Decorated function.

    Example:
        @trace_async(name="analyze_frame", attributes={"component": "proctor"})
        async def analyze_frame(frame_data):
            ...
    """

    def decorator(func: F) -> F:
        if not OTEL_AVAILABLE:
            return func

        span_name = name or func.__name__
        span_kind = kind or SpanKind.INTERNAL
        tracer = get_tracer(func.__module__)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                span_name,
                kind=span_kind,
                attributes=attributes,
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


class SpanContext:
    """Context manager for creating spans.

    Example:
        with SpanContext("process_batch") as span:
            span.set_attribute("batch_size", len(items))
            process_items(items)
    """

    def __init__(
        self,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
        tracer_name: str = "biometric-processor",
    ):
        """Initialize span context.

        Args:
            name: Span name.
            kind: Span kind.
            attributes: Initial attributes.
            tracer_name: Name of the tracer.
        """
        self.name = name
        self.kind = kind or (SpanKind.INTERNAL if OTEL_AVAILABLE else None)
        self.attributes = attributes or {}
        self.tracer_name = tracer_name
        self._span = None
        self._token = None

    def __enter__(self):
        if not OTEL_AVAILABLE:
            return _NoOpSpan()

        tracer = get_tracer(self.tracer_name)
        self._span = tracer.start_span(
            self.name,
            kind=self.kind,
            attributes=self.attributes,
        )
        self._token = trace.context.attach(
            set_span_in_context(self._span)
        )
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not OTEL_AVAILABLE or not self._span:
            return False

        if exc_val:
            self._span.record_exception(exc_val)
            self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
        else:
            self._span.set_status(Status(StatusCode.OK))

        self._span.end()

        if self._token:
            trace.context.detach(self._token)

        return False


class _NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: Dict[str, Any]) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def is_recording(self) -> bool:
        return False


# Span attribute constants for consistent naming
class SpanAttributes:
    """Standard span attribute names."""

    # Service attributes
    USER_ID = "user.id"
    TENANT_ID = "tenant.id"
    SESSION_ID = "session.id"

    # Biometric attributes
    IMAGE_SIZE = "biometric.image.size"
    IMAGE_FORMAT = "biometric.image.format"
    FACE_COUNT = "biometric.face.count"
    LIVENESS_SCORE = "biometric.liveness.score"
    SIMILARITY_SCORE = "biometric.similarity.score"
    QUALITY_SCORE = "biometric.quality.score"

    # Proctoring attributes
    PROCTOR_SESSION_ID = "proctoring.session.id"
    PROCTOR_EXAM_ID = "proctoring.exam.id"
    PROCTOR_INCIDENT_TYPE = "proctoring.incident.type"
    PROCTOR_RISK_SCORE = "proctoring.risk.score"
    PROCTOR_FRAME_NUMBER = "proctoring.frame.number"

    # ML attributes
    ML_MODEL = "ml.model.name"
    ML_INFERENCE_TIME = "ml.inference.time_ms"
    ML_CONFIDENCE = "ml.confidence"

    # Database attributes
    DB_OPERATION = "db.operation"
    DB_TABLE = "db.table"
    DB_ROWS_AFFECTED = "db.rows_affected"
