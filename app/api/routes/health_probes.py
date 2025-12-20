"""Health probe endpoints for Kubernetes-style readiness and liveness checks.

Provides:
- /ready - Readiness probe (checks all dependencies)
- /live - Liveness probe (basic app health)
- /health/detailed - Detailed health with all component statuses
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.metrics import (
    get_infrastructure_monitor,
    HealthStatus,
    ComponentHealth,
    SystemHealth,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


class ComponentHealthResponse(BaseModel):
    """Response model for component health."""

    name: str
    status: str
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = {}


class DetailedHealthResponse(BaseModel):
    """Response model for detailed health check."""

    status: str
    version: str
    environment: str
    uptime_seconds: float
    is_ready: bool
    is_live: bool
    components: List[ComponentHealthResponse]


class ReadinessResponse(BaseModel):
    """Response model for readiness probe."""

    ready: bool
    checks: Dict[str, str]


class LivenessResponse(BaseModel):
    """Response model for liveness probe."""

    alive: bool
    status: str


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Service is ready to accept traffic"},
        503: {"description": "Service is not ready"},
    },
)
async def readiness_probe() -> Response:
    """Kubernetes readiness probe.

    Checks if the service is ready to accept traffic by verifying
    all critical dependencies (database, Redis, ML models).

    Returns:
        ReadinessResponse with ready status
    """
    monitor = get_infrastructure_monitor()
    health = await monitor.check_health()

    checks = {}
    for component in health.components:
        checks[component.name] = component.status.value

    response_data = ReadinessResponse(
        ready=health.is_ready,
        checks=checks,
    )

    if health.is_ready:
        return Response(
            content=response_data.model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
    else:
        return Response(
            content=response_data.model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get(
    "/live",
    response_model=LivenessResponse,
    responses={
        200: {"description": "Service is alive"},
        503: {"description": "Service is not responding"},
    },
)
async def liveness_probe() -> Response:
    """Kubernetes liveness probe.

    Basic health check to verify the service is alive and responding.
    Does not check external dependencies.

    Returns:
        LivenessResponse with alive status
    """
    # Basic liveness - just check if the app can respond
    try:
        # Quick internal check
        from app.core.metrics import get_process_collector
        collector = get_process_collector()
        collector.collect()  # Trigger a collection to verify internals work

        response_data = LivenessResponse(
            alive=True,
            status="healthy",
        )
        return Response(
            content=response_data.model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Liveness probe failed: {e}")
        response_data = LivenessResponse(
            alive=False,
            status="unhealthy",
        )
        return Response(
            content=response_data.model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    responses={
        200: {"description": "Detailed health status"},
        503: {"description": "Service unhealthy"},
    },
)
async def detailed_health() -> Response:
    """Detailed health check with all component statuses.

    Provides comprehensive health information including:
    - Overall status
    - Individual component health
    - Latency metrics
    - Detailed diagnostics

    Returns:
        DetailedHealthResponse with full health details
    """
    import time
    from app.core.metrics import PROCESS_UPTIME

    monitor = get_infrastructure_monitor()
    health = await monitor.check_health()

    # Get uptime
    try:
        uptime = PROCESS_UPTIME._value.get()
    except Exception:
        uptime = 0.0

    components = [
        ComponentHealthResponse(
            name=c.name,
            status=c.status.value,
            latency_ms=c.latency_ms,
            message=c.message,
            details=c.details,
        )
        for c in health.components
    ]

    response_data = DetailedHealthResponse(
        status=health.status.value,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=uptime,
        is_ready=health.is_ready,
        is_live=health.is_live,
        components=components,
    )

    status_code = (
        status.HTTP_200_OK
        if health.status != HealthStatus.UNHEALTHY
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return Response(
        content=response_data.model_dump_json(),
        media_type="application/json",
        status_code=status_code,
    )
