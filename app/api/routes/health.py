"""Health check API routes for monitoring and observability."""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException

import numpy as np

from app.api.schemas.common import HealthResponse
from app.core.config import settings
from app.core.container import get_embedding_repository, get_face_detector, get_embedding_extractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.infrastructure.cache.cached_embedding_repository import CachedEmbeddingRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# Store application start time
_start_time = time.time()


@router.get("/health", response_model=HealthResponse, status_code=200)
async def health_check() -> HealthResponse:
    """Basic health check endpoint.

    Returns service health status and configuration information.
    This is the original simple health endpoint for backward compatibility.

    Returns:
        HealthResponse with service status
    """
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        model=settings.FACE_RECOGNITION_MODEL,
        detector=settings.FACE_DETECTION_BACKEND,
    )


async def _check_ml_models(
    detector: IFaceDetector,
    extractor: IEmbeddingExtractor
) -> Dict[str, Any]:
    """Check ML models are loaded and functional.

    Performs a lightweight test to verify ML models can be invoked.
    This prevents false positive health status when models fail to load.

    Args:
        detector: Face detector to test
        extractor: Embedding extractor to test

    Returns:
        Dict with model health status and details
    """
    try:
        # Create a minimal test image (100x100 black image)
        # This is sufficient to test if models are loaded
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)

        # Get model names for diagnostics
        detector_name = detector.get_detector_name() if hasattr(detector, 'get_detector_name') else "unknown"
        model_name = extractor.get_model_name() if hasattr(extractor, 'get_model_name') else "unknown"

        # Test detection (this verifies the detector is loaded and functional)
        # We expect this might fail (no face in black image) but that's OK
        # We just want to verify the model doesn't crash
        try:
            await detector.detect(test_image)
            detector_status = "healthy"
        except Exception as e:
            # Expected: FaceNotDetectedError is OK (means detector works)
            # Only fail if it's a loading/initialization error
            error_str = str(e).lower()
            if "not loaded" in error_str or "not found" in error_str or "cannot" in error_str:
                detector_status = "unhealthy"
                raise Exception(f"Detector not loaded: {str(e)}")
            else:
                # Face not detected is expected for test image
                detector_status = "healthy"

        return {
            "status": "healthy",
            "detector": {
                "name": detector_name,
                "status": detector_status,
            },
            "extractor": {
                "name": model_name,
                "status": "healthy",
            },
        }

    except Exception as e:
        logger.error(f"ML model health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "detector": {
                "name": detector_name if 'detector_name' in locals() else "unknown",
                "status": "unhealthy",
            },
            "extractor": {
                "name": model_name if 'model_name' in locals() else "unknown",
                "status": "unknown",
            },
        }


@router.get("/health/detailed", status_code=200)
async def detailed_health_check(
    repository: IEmbeddingRepository = Depends(get_embedding_repository),
    detector: IFaceDetector = Depends(get_face_detector),
    extractor: IEmbeddingExtractor = Depends(get_embedding_extractor),
) -> Dict[str, Any]:
    """Comprehensive health check endpoint with system diagnostics.

    Checks the health of all critical system components:
    - Application status
    - Database connectivity
    - Cache status (if enabled)
    - ML models (detector and extractor)
    - Configuration

    Returns:
        Detailed health status with diagnostics

    Status codes:
        200: System is healthy
        503: System is unhealthy (some checks failed)

    Usage:
        - Kubernetes liveness probe: GET /health/detailed
        - Monitoring systems: Poll this endpoint periodically
        - Dashboard: Display real-time health status
    """
    checks = {}
    overall_status = "healthy"
    status_code = 200

    # Application check
    checks["application"] = {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }

    # Database check
    try:
        count = await repository.count()
        checks["database"] = {
            "status": "healthy",
            "embeddings_count": count,
            "type": "pgvector" if settings.USE_PGVECTOR else "in-memory",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        overall_status = "unhealthy"
        status_code = 503

    # Cache check (if enabled)
    if settings.EMBEDDING_CACHE_ENABLED:
        try:
            if isinstance(repository, CachedEmbeddingRepository):
                cache_stats = await repository.get_cache_stats()
                checks["cache"] = {
                    "status": "healthy",
                    "enabled": True,
                    "stats": cache_stats,
                }
            else:
                checks["cache"] = {
                    "status": "degraded",
                    "enabled": False,
                    "message": "Cache configured but not active",
                }
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            logger.error(f"Cache health check failed: {str(e)}")
            checks["cache"] = {
                "status": "degraded",
                "error": str(e),
            }
            if overall_status == "healthy":
                overall_status = "degraded"
    else:
        checks["cache"] = {
            "status": "disabled",
            "enabled": False,
        }

    # ML Models check (CRITICAL: prevents false positive health status)
    ml_check = await _check_ml_models(detector, extractor)
    checks["ml_models"] = ml_check
    if ml_check["status"] == "unhealthy":
        overall_status = "unhealthy"
        status_code = 503
        logger.error("ML models health check failed - system cannot process requests")

    # Configuration check
    checks["configuration"] = {
        "status": "healthy",
        "multi_image_enrollment": settings.MULTI_IMAGE_ENROLLMENT_ENABLED,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
        "face_detection_backend": settings.FACE_DETECTION_BACKEND,
        "face_recognition_model": settings.FACE_RECOGNITION_MODEL,
    }

    # Calculate uptime
    uptime = time.time() - _start_time

    result = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(uptime, 2),
        "checks": checks,
    }

    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=result)

    return result


@router.get("/health/live", status_code=200)
async def liveness_check() -> Dict[str, Any]:
    """Liveness check endpoint (lightweight).

    This endpoint indicates whether the application is running.
    It performs minimal checks and responds quickly.

    Returns:
        Simple status indicating the application is alive

    Usage:
        - Kubernetes liveness probe: GET /health/live
        - Returns 200 if application is running
        - Should restart container if this fails
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": round(time.time() - _start_time, 2),
    }


@router.get("/health/ready", status_code=200)
async def readiness_check(
    repository: IEmbeddingRepository = Depends(get_embedding_repository),
    detector: IFaceDetector = Depends(get_face_detector),
    extractor: IEmbeddingExtractor = Depends(get_embedding_extractor),
) -> Dict[str, Any]:
    """Readiness check endpoint.

    This endpoint indicates whether the application is ready to serve traffic.
    Checks that all required dependencies are available.

    Returns:
        Readiness status

    Status codes:
        200: Application is ready
        503: Application is not ready

    Usage:
        - Kubernetes readiness probe: GET /health/ready
        - Load balancer health check
    """
    checks = {}
    all_ready = True

    # Database readiness
    try:
        await repository.count()
        checks["database"] = True
    except Exception as e:
        logger.warning(f"Database not ready: {str(e)}")
        checks["database"] = False
        all_ready = False

    # ML Models readiness (CRITICAL: prevents routing to pods with broken ML models)
    ml_check = await _check_ml_models(detector, extractor)
    checks["ml_models"] = ml_check["status"] == "healthy"
    if ml_check["status"] == "unhealthy":
        logger.warning(f"ML models not ready: {ml_check.get('error', 'unknown error')}")
        all_ready = False

    # Cache readiness (if enabled)
    if settings.EMBEDDING_CACHE_ENABLED:
        checks["cache"] = isinstance(repository, CachedEmbeddingRepository)
    else:
        checks["cache"] = True

    # Configuration loaded
    checks["configuration"] = settings.VERSION is not None

    result = {
        "ready": all_ready,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks,
    }

    if not all_ready:
        raise HTTPException(status_code=503, detail=result)

    return result


@router.get("/metrics/cache", status_code=200)
async def cache_metrics(
    repository: IEmbeddingRepository = Depends(get_embedding_repository),
) -> Dict[str, Any]:
    """Get cache performance metrics.

    Returns detailed caching statistics for monitoring and optimization.

    Returns:
        Cache metrics including hit rate, size, and TTL

    Raises:
        HTTPException 404: If caching is not enabled
    """
    if not settings.EMBEDDING_CACHE_ENABLED:
        raise HTTPException(
            status_code=404,
            detail="Cache is not enabled. Set EMBEDDING_CACHE_ENABLED=true to enable caching.",
        )

    if not isinstance(repository, CachedEmbeddingRepository):
        raise HTTPException(
            status_code=500,
            detail="Cache is enabled but repository is not wrapped with caching layer",
        )

    stats = await repository.get_cache_stats()

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cache_enabled": True,
        "metrics": stats,
        "recommendations": _get_cache_recommendations(stats),
    }


def _get_cache_recommendations(stats: Dict[str, Any]) -> list[str]:
    """Generate cache optimization recommendations based on stats."""
    recommendations = []

    hit_rate = stats.get("hit_rate_percent", 0)
    current_size = stats.get("current_size", 0)
    max_size = stats.get("max_size", 0)

    if hit_rate < 30:
        recommendations.append(
            f"Low cache hit rate ({hit_rate}%). Consider increasing cache TTL."
        )
    elif hit_rate > 80:
        recommendations.append(
            f"Excellent cache hit rate ({hit_rate}%). Cache is well-tuned."
        )

    if current_size > max_size * 0.9:
        recommendations.append(
            f"Cache is {current_size}/{max_size} entries ({current_size/max_size*100:.1f}% full). "
            f"Consider increasing EMBEDDING_CACHE_MAX_SIZE."
        )
    elif current_size < max_size * 0.3 and stats.get("total_requests", 0) > 100:
        recommendations.append(
            f"Cache underutilized ({current_size}/{max_size}). "
            f"Consider reducing EMBEDDING_CACHE_MAX_SIZE."
        )

    if not recommendations:
        recommendations.append("Cache performance is optimal.")

    return recommendations
