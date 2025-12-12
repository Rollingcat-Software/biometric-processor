"""OpenTelemetry tracing configuration and setup.

This module configures distributed tracing using OpenTelemetry.
Supports multiple exporters: OTLP, Jaeger, Zipkin, and Console.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TracingExporter(str, Enum):
    """Supported tracing exporters."""

    OTLP = "otlp"
    JAEGER = "jaeger"
    ZIPKIN = "zipkin"
    CONSOLE = "console"
    NONE = "none"


@dataclass
class TracingConfig:
    """OpenTelemetry tracing configuration.

    Attributes:
        enabled: Whether tracing is enabled.
        service_name: Name of the service for trace identification.
        service_version: Version of the service.
        exporter: Tracing exporter to use.
        endpoint: Exporter endpoint URL.
        sample_rate: Sampling rate (0.0 to 1.0).
        propagators: List of context propagators.
        resource_attributes: Additional resource attributes.
    """

    enabled: bool = True
    service_name: str = "biometric-processor"
    service_version: str = "1.0.0"
    exporter: TracingExporter = TracingExporter.OTLP
    endpoint: str = "http://localhost:4317"
    sample_rate: float = 1.0
    propagators: List[str] = field(
        default_factory=lambda: ["tracecontext", "baggage"]
    )
    resource_attributes: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "TracingConfig":
        """Create config from environment variables.

        Environment variables:
            OTEL_ENABLED: Enable/disable tracing (default: true)
            OTEL_SERVICE_NAME: Service name
            OTEL_SERVICE_VERSION: Service version
            OTEL_EXPORTER: Exporter type (otlp, jaeger, zipkin, console)
            OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint
            OTEL_SAMPLE_RATE: Sampling rate (0.0-1.0)
        """
        import os

        return cls(
            enabled=os.getenv("OTEL_ENABLED", "true").lower() == "true",
            service_name=os.getenv("OTEL_SERVICE_NAME", "biometric-processor"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            exporter=TracingExporter(
                os.getenv("OTEL_EXPORTER", "otlp").lower()
            ),
            endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
            ),
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
            resource_attributes={
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
                "host.name": os.getenv("HOSTNAME", "unknown"),
            },
        )


def setup_tracing(config: Optional[TracingConfig] = None) -> bool:
    """Set up OpenTelemetry tracing.

    Args:
        config: Tracing configuration. If None, loads from environment.

    Returns:
        True if tracing was successfully configured, False otherwise.
    """
    if config is None:
        config = TracingConfig.from_env()

    if not config.enabled or config.exporter == TracingExporter.NONE:
        logger.info("Tracing is disabled")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        from opentelemetry.baggage.propagation import W3CBaggagePropagator
    except ImportError:
        logger.warning(
            "OpenTelemetry not installed. Run: pip install opentelemetry-sdk "
            "opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi"
        )
        return False

    # Create resource with service info
    resource_attrs = {
        SERVICE_NAME: config.service_name,
        SERVICE_VERSION: config.service_version,
        **config.resource_attributes,
    }
    resource = Resource.create(resource_attrs)

    # Create sampler
    sampler = TraceIdRatioBased(config.sample_rate)

    # Create tracer provider
    tracer_provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )

    # Configure exporter
    span_processor = _create_span_processor(config)
    if span_processor:
        tracer_provider.add_span_processor(span_processor)

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)

    # Configure propagators
    propagators = []
    if "tracecontext" in config.propagators:
        propagators.append(TraceContextTextMapPropagator())
    if "baggage" in config.propagators:
        propagators.append(W3CBaggagePropagator())

    if propagators:
        set_global_textmap(CompositePropagator(propagators))

    logger.info(
        f"Tracing configured: service={config.service_name}, "
        f"exporter={config.exporter.value}, sample_rate={config.sample_rate}"
    )
    return True


def _create_span_processor(config: TracingConfig):
    """Create span processor based on exporter type."""
    try:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

        if config.exporter == TracingExporter.OTLP:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=config.endpoint)
            return BatchSpanProcessor(exporter)

        elif config.exporter == TracingExporter.JAEGER:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter

            # Parse Jaeger endpoint
            host, port = config.endpoint.replace("http://", "").split(":")
            exporter = JaegerExporter(
                agent_host_name=host,
                agent_port=int(port),
            )
            return BatchSpanProcessor(exporter)

        elif config.exporter == TracingExporter.ZIPKIN:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter

            exporter = ZipkinExporter(endpoint=config.endpoint)
            return BatchSpanProcessor(exporter)

        elif config.exporter == TracingExporter.CONSOLE:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            exporter = ConsoleSpanExporter()
            return SimpleSpanProcessor(exporter)

    except ImportError as e:
        logger.warning(f"Failed to create exporter: {e}")
        return None

    return None


def instrument_fastapi(app) -> None:
    """Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,metrics",
        )
        logger.info("FastAPI instrumented with OpenTelemetry")
    except ImportError:
        logger.warning(
            "FastAPI instrumentation not available. "
            "Run: pip install opentelemetry-instrumentation-fastapi"
        )
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")


def instrument_httpx() -> None:
    """Instrument httpx HTTP client."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx instrumented with OpenTelemetry")
    except ImportError:
        pass


def instrument_asyncpg() -> None:
    """Instrument asyncpg database client."""
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
        logger.info("asyncpg instrumented with OpenTelemetry")
    except ImportError:
        pass


def instrument_redis() -> None:
    """Instrument Redis client."""
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
        logger.info("Redis instrumented with OpenTelemetry")
    except ImportError:
        pass
