"""Prometheus metrics definitions and collector."""

import logging
import time
from contextlib import contextmanager
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Metric Definitions
# ============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    "biometric_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "biometric_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

ACTIVE_REQUESTS = Gauge(
    "biometric_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "endpoint"],
)

# Face operation metrics
FACE_OPERATIONS = Counter(
    "biometric_face_operations_total",
    "Total face operations",
    ["operation", "status"],
)

ML_INFERENCE_TIME = Histogram(
    "biometric_ml_inference_seconds",
    "ML model inference time in seconds",
    ["model", "operation"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Storage metrics
EMBEDDING_STORAGE_SIZE = Gauge(
    "biometric_embedding_storage_count",
    "Number of embeddings in storage",
    ["tenant_id"],
)

# Error metrics
ERROR_COUNT = Counter(
    "biometric_errors_total",
    "Total errors by type",
    ["error_type", "endpoint"],
)

# Rate limiting metrics
RATE_LIMIT_HITS = Counter(
    "biometric_rate_limit_hits_total",
    "Total rate limit hits",
    ["tier", "endpoint"],
)

# Application info
APP_INFO = Info(
    "biometric_app",
    "Application information",
)


class MetricsCollector:
    """Centralized metrics collection and management.

    Provides helper methods for recording metrics across the application.
    """

    def __init__(self):
        """Initialize the metrics collector."""
        self._initialized = False

    def init(self, app_name: str, version: str, environment: str) -> None:
        """Initialize application info metrics.

        Args:
            app_name: Application name
            version: Application version
            environment: Environment name
        """
        if self._initialized:
            return

        APP_INFO.info({
            "app_name": app_name,
            "version": version,
            "environment": environment,
        })
        self._initialized = True
        logger.info("Metrics collector initialized")

    @contextmanager
    def track_request(self, method: str, endpoint: str):
        """Context manager to track request metrics.

        Args:
            method: HTTP method
            endpoint: Request endpoint

        Yields:
            Context for the request
        """
        ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.time()

        try:
            yield
        finally:
            duration = time.time() - start_time
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).dec()

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: Optional[float] = None,
    ) -> None:
        """Record a completed request.

        Args:
            method: HTTP method
            endpoint: Request endpoint
            status_code: Response status code
            duration: Request duration in seconds
        """
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()

        if duration is not None:
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    def record_face_operation(
        self,
        operation: str,
        success: bool,
    ) -> None:
        """Record a face operation.

        Args:
            operation: Operation type (detect, enroll, verify, etc.)
            success: Whether the operation succeeded
        """
        status = "success" if success else "failure"
        FACE_OPERATIONS.labels(operation=operation, status=status).inc()

    @contextmanager
    def track_inference(self, model: str, operation: str):
        """Context manager to track ML inference time.

        Args:
            model: Model name
            operation: Operation type

        Yields:
            Context for the inference
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            ML_INFERENCE_TIME.labels(model=model, operation=operation).observe(duration)

    def record_inference_time(
        self,
        model: str,
        operation: str,
        duration: float,
    ) -> None:
        """Record ML inference time.

        Args:
            model: Model name
            operation: Operation type
            duration: Inference duration in seconds
        """
        ML_INFERENCE_TIME.labels(model=model, operation=operation).observe(duration)

    def set_storage_size(self, tenant_id: str, count: int) -> None:
        """Set the embedding storage size for a tenant.

        Args:
            tenant_id: Tenant identifier
            count: Number of embeddings
        """
        EMBEDDING_STORAGE_SIZE.labels(tenant_id=tenant_id).set(count)

    def record_error(self, error_type: str, endpoint: str) -> None:
        """Record an error.

        Args:
            error_type: Type of error
            endpoint: Endpoint where error occurred
        """
        ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()

    def record_rate_limit(self, tier: str, endpoint: str) -> None:
        """Record a rate limit hit.

        Args:
            tier: Rate limit tier
            endpoint: Endpoint that was rate limited
        """
        RATE_LIMIT_HITS.labels(tier=tier, endpoint=endpoint).inc()

    @staticmethod
    def get_metrics() -> bytes:
        """Get Prometheus metrics output.

        Returns:
            Prometheus metrics in text format
        """
        return generate_latest(REGISTRY)

    @staticmethod
    def get_content_type() -> str:
        """Get Prometheus content type.

        Returns:
            Content type string
        """
        return CONTENT_TYPE_LATEST


# Singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        MetricsCollector singleton
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def init_metrics(app_name: str, version: str, environment: str) -> MetricsCollector:
    """Initialize the global metrics collector.

    Args:
        app_name: Application name
        version: Application version
        environment: Environment name

    Returns:
        Initialized MetricsCollector
    """
    collector = get_metrics()
    collector.init(app_name, version, environment)
    return collector
