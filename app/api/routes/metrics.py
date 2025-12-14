"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response

from app.core.config import settings
from app.core.metrics import get_metrics

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.

    Returns:
        Prometheus metrics response
    """
    metrics = get_metrics()

    return Response(
        content=metrics.get_metrics(),
        media_type=metrics.get_content_type(),
    )
