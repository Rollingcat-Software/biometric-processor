"""Health check API routes."""

import logging
from fastapi import APIRouter

from app.api.schemas.common import HealthResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, status_code=200)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns service health status and configuration information.

    Returns:
        HealthResponse with service status
    """
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        model=settings.FACE_RECOGNITION_MODEL,
        detector=settings.FACE_DETECTION_BACKEND,
    )
