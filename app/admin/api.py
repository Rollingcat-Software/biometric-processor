"""Admin API endpoints for monitoring and management.

Provides RESTful API for admin dashboard functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

admin_api_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================================
# Response Models
# ============================================================================


class SystemHealthResponse(BaseModel):
    """System health check response."""

    status: str
    timestamp: str
    components: Dict[str, Dict[str, Any]]


class DashboardMetricsResponse(BaseModel):
    """Dashboard metrics response."""

    timestamp: str
    period: str
    enrollments: Dict[str, int]
    verifications: Dict[str, int]
    proctoring: Dict[str, int]
    performance: Dict[str, float]


class SessionListResponse(BaseModel):
    """Proctoring session list response."""

    total: int
    page: int
    page_size: int
    sessions: List[Dict[str, Any]]


class IncidentListResponse(BaseModel):
    """Incident list response."""

    total: int
    page: int
    page_size: int
    incidents: List[Dict[str, Any]]


class TenantStatsResponse(BaseModel):
    """Tenant statistics response."""

    tenant_id: str
    stats: Dict[str, Any]


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@admin_api_router.get("/health", response_model=SystemHealthResponse)
async def get_system_health() -> SystemHealthResponse:
    """Get comprehensive system health status.

    Returns health status of all system components.
    """
    components = {}

    # Check API health
    components["api"] = {"status": "healthy", "latency_ms": 1.2}

    # Check database (simulated)
    try:
        components["database"] = {
            "status": "healthy",
            "connections": 5,
            "pool_size": 10,
        }
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}

    # Check Redis (simulated)
    try:
        components["redis"] = {
            "status": "healthy",
            "connected": True,
            "memory_mb": 128,
        }
    except Exception as e:
        components["redis"] = {"status": "unhealthy", "error": str(e)}

    # Check Celery workers (simulated)
    try:
        from app.workers.celery_app import check_celery_health

        celery_health = check_celery_health()
        components["celery"] = celery_health
    except Exception as e:
        components["celery"] = {"status": "unknown", "error": str(e)}

    # Determine overall status
    overall_status = "healthy"
    for comp in components.values():
        if comp.get("status") == "unhealthy":
            overall_status = "degraded"
            break

    return SystemHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        components=components,
    )


# ============================================================================
# Dashboard Metrics Endpoints
# ============================================================================


@admin_api_router.get("/metrics/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    period: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
) -> DashboardMetricsResponse:
    """Get dashboard metrics for specified period.

    Args:
        period: Time period (1h, 24h, 7d, 30d).

    Returns:
        Aggregated metrics for the period.
    """
    # Calculate time range
    now = datetime.utcnow()
    if period == "1h":
        start = now - timedelta(hours=1)
    elif period == "24h":
        start = now - timedelta(days=1)
    elif period == "7d":
        start = now - timedelta(days=7)
    else:  # 30d
        start = now - timedelta(days=30)

    # Simulated metrics (in production, query from database)
    return DashboardMetricsResponse(
        timestamp=now.isoformat(),
        period=period,
        enrollments={
            "total": 1250,
            "successful": 1180,
            "failed": 70,
            "rate_per_hour": 52.1,
        },
        verifications={
            "total": 8500,
            "matched": 7800,
            "not_matched": 700,
            "avg_confidence": 0.92,
        },
        proctoring={
            "active_sessions": 45,
            "completed_sessions": 320,
            "total_incidents": 89,
            "critical_incidents": 5,
        },
        performance={
            "avg_response_time_ms": 125.5,
            "p95_response_time_ms": 280.0,
            "p99_response_time_ms": 450.0,
            "requests_per_second": 85.2,
        },
    )


@admin_api_router.get("/metrics/realtime")
async def get_realtime_metrics() -> Dict[str, Any]:
    """Get real-time system metrics.

    Returns current system state metrics.
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": 127,
        "requests_in_flight": 15,
        "queue_depth": {
            "default": 5,
            "batch": 12,
            "proctoring": 23,
        },
        "memory_usage_mb": 512,
        "cpu_percent": 35.5,
        "gpu_utilization_percent": 68.2,
    }


# ============================================================================
# Session Management Endpoints
# ============================================================================


@admin_api_router.get("/sessions", response_model=SessionListResponse)
async def list_proctoring_sessions(
    status: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SessionListResponse:
    """List proctoring sessions with filtering.

    Args:
        status: Filter by session status.
        tenant_id: Filter by tenant.
        page: Page number.
        page_size: Items per page.

    Returns:
        Paginated session list.
    """
    # Simulated session data
    sessions = [
        {
            "id": f"session-{i}",
            "exam_id": f"exam-{i % 10}",
            "user_id": f"user-{i % 50}",
            "status": ["started", "completed", "flagged"][i % 3],
            "risk_score": round(0.1 + (i % 10) * 0.08, 2),
            "incident_count": i % 5,
            "started_at": (datetime.utcnow() - timedelta(hours=i)).isoformat(),
        }
        for i in range(page_size)
    ]

    return SessionListResponse(
        total=150,
        page=page,
        page_size=page_size,
        sessions=sessions,
    )


@admin_api_router.get("/sessions/{session_id}")
async def get_session_details(session_id: str) -> Dict[str, Any]:
    """Get detailed session information.

    Args:
        session_id: Session identifier.

    Returns:
        Session details with incidents and timeline.
    """
    return {
        "id": session_id,
        "exam_id": "exam-001",
        "user_id": "user-123",
        "tenant_id": "tenant-abc",
        "status": "completed",
        "started_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
        "duration_minutes": 120,
        "frame_count": 7200,
        "risk_score": 0.35,
        "integrity_score": 0.85,
        "incidents": [
            {
                "type": "gaze_away_prolonged",
                "severity": "medium",
                "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            }
        ],
        "verification_attempts": 3,
        "successful_verifications": 3,
    }


@admin_api_router.post("/sessions/{session_id}/terminate")
async def terminate_session(
    session_id: str,
    reason: str = Query(..., min_length=10),
) -> Dict[str, str]:
    """Terminate an active proctoring session.

    Args:
        session_id: Session to terminate.
        reason: Termination reason.

    Returns:
        Termination confirmation.
    """
    logger.info(f"Admin terminating session {session_id}: {reason}")
    return {
        "status": "terminated",
        "session_id": session_id,
        "reason": reason,
        "terminated_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Incident Management Endpoints
# ============================================================================


@admin_api_router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    severity: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> IncidentListResponse:
    """List incidents with filtering.

    Args:
        severity: Filter by severity.
        incident_type: Filter by type.
        review_status: Filter by review status.
        page: Page number.
        page_size: Items per page.

    Returns:
        Paginated incident list.
    """
    incidents = [
        {
            "id": f"incident-{i}",
            "session_id": f"session-{i % 20}",
            "type": ["gaze_away_prolonged", "object_detected", "multiple_faces"][i % 3],
            "severity": ["low", "medium", "high", "critical"][i % 4],
            "review_status": ["pending", "confirmed", "dismissed"][i % 3],
            "detected_at": (datetime.utcnow() - timedelta(hours=i)).isoformat(),
        }
        for i in range(page_size)
    ]

    return IncidentListResponse(
        total=89,
        page=page,
        page_size=page_size,
        incidents=incidents,
    )


@admin_api_router.post("/incidents/{incident_id}/review")
async def review_incident(
    incident_id: str,
    action: str = Query(..., regex="^(dismiss|confirm|escalate)$"),
    notes: Optional[str] = Query(None),
) -> Dict[str, str]:
    """Review and take action on an incident.

    Args:
        incident_id: Incident to review.
        action: Review action (dismiss, confirm, escalate).
        notes: Optional review notes.

    Returns:
        Review confirmation.
    """
    logger.info(f"Admin reviewing incident {incident_id}: {action}")
    return {
        "status": "reviewed",
        "incident_id": incident_id,
        "action": action,
        "reviewed_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Tenant Management Endpoints
# ============================================================================


@admin_api_router.get("/tenants/{tenant_id}/stats", response_model=TenantStatsResponse)
async def get_tenant_stats(tenant_id: str) -> TenantStatsResponse:
    """Get statistics for a specific tenant.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        Tenant usage statistics.
    """
    return TenantStatsResponse(
        tenant_id=tenant_id,
        stats={
            "enrollments": {"total": 5000, "active": 4800},
            "verifications": {"total": 150000, "success_rate": 0.94},
            "proctoring_sessions": {"total": 2500, "flagged": 45},
            "storage_used_gb": 25.5,
            "api_calls_month": 500000,
        },
    )


# ============================================================================
# Configuration Endpoints
# ============================================================================


@admin_api_router.get("/config")
async def get_system_config() -> Dict[str, Any]:
    """Get current system configuration.

    Returns:
        System configuration (non-sensitive).
    """
    return {
        "ml_models": {
            "face_detector": "opencv_dnn",
            "embedding_model": "facenet",
            "liveness_detector": "combined",
        },
        "thresholds": {
            "similarity": 0.6,
            "liveness": 60.0,
            "quality": 0.7,
        },
        "proctoring": {
            "gaze_threshold_seconds": 3.0,
            "risk_threshold": 0.7,
            "max_incidents": 10,
        },
        "limits": {
            "max_batch_size": 100,
            "max_image_size_mb": 10,
            "session_timeout_hours": 4,
        },
    }


@admin_api_router.post("/config/reload")
async def reload_configuration() -> Dict[str, str]:
    """Reload system configuration from sources.

    Returns:
        Reload confirmation.
    """
    logger.info("Admin triggered configuration reload")
    return {
        "status": "reloaded",
        "reloaded_at": datetime.utcnow().isoformat(),
    }
