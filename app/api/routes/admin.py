"""Admin API routes for system statistics and monitoring."""

import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.container import get_embedding_repository
from app.api.middleware.jwt_auth import require_auth, AuthContext
from app.domain.interfaces.embedding_repository import IEmbeddingRepository

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)

import threading

# Track metrics in memory (would use Redis in production)
_metrics_lock = threading.Lock()
_metrics = {
    "total_verifications": 0,
    "successful_verifications": 0,
    "total_searches": 0,
    "total_liveness_checks": 0,
    "spoofs_detected": 0,
    "api_calls_today": 0,
    "api_calls_this_week": 0,
    "start_time": time.time(),
    "response_times": [],
    "activities": [],
}


class SystemStats(BaseModel):
    """System statistics response."""
    total_enrollments: int
    total_verifications: int
    total_searches: int
    active_sessions: int
    api_calls_today: int
    api_calls_this_week: int
    average_response_time_ms: float
    storage_used_gb: float
    uptime_hours: float
    verification_success_rate: float
    spoof_detection_rate: float


class Activity(BaseModel):
    """Activity log entry."""
    id: str
    type: str
    user_id: Optional[str] = None
    timestamp: str
    details: Optional[dict] = None


class RecentActivity(BaseModel):
    """Recent activity response."""
    activities: List[Activity]


def record_activity(activity_type: str, user_id: Optional[str] = None, details: Optional[dict] = None):
    """Record an activity for the activity log (thread-safe)."""
    activity = {
        "id": f"act-{int(time.time() * 1000)}",
        "type": activity_type,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "details": details,
    }
    with _metrics_lock:
        _metrics["activities"].insert(0, activity)
        # Keep only last 100 activities
        _metrics["activities"] = _metrics["activities"][:100]


def record_api_call(response_time_ms: float):
    """Record an API call for metrics (thread-safe)."""
    with _metrics_lock:
        _metrics["api_calls_today"] += 1
        _metrics["api_calls_this_week"] += 1
        _metrics["response_times"].append(response_time_ms)
        # Keep only last 1000 response times
        _metrics["response_times"] = _metrics["response_times"][-1000:]


def record_verification(success: bool):
    """Record a verification attempt (thread-safe)."""
    with _metrics_lock:
        _metrics["total_verifications"] += 1
        if success:
            _metrics["successful_verifications"] += 1


def record_search():
    """Record a search operation (thread-safe)."""
    with _metrics_lock:
        _metrics["total_searches"] += 1


def record_liveness_check(is_spoof: bool):
    """Record a liveness check (thread-safe)."""
    with _metrics_lock:
        _metrics["total_liveness_checks"] += 1
        if is_spoof:
            _metrics["spoofs_detected"] += 1


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    auth: AuthContext = Depends(require_auth),
    repository: IEmbeddingRepository = Depends(get_embedding_repository),
) -> SystemStats:
    """Get system statistics.

    Returns real-time statistics about the biometric system including
    enrollment counts, verification metrics, and system health.
    """
    # Get real enrollment count from repository
    total_enrollments = await repository.count()

    # Calculate uptime
    uptime_seconds = time.time() - _metrics["start_time"]
    uptime_hours = uptime_seconds / 3600

    # Calculate average response time
    response_times = _metrics["response_times"]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0

    # Calculate rates
    total_verifications = _metrics["total_verifications"]
    successful_verifications = _metrics["successful_verifications"]
    verification_success_rate = (
        (successful_verifications / total_verifications * 100)
        if total_verifications > 0 else 0
    )

    total_liveness = _metrics["total_liveness_checks"]
    spoofs = _metrics["spoofs_detected"]
    spoof_rate = (spoofs / total_liveness * 100) if total_liveness > 0 else 0

    return SystemStats(
        total_enrollments=total_enrollments,
        total_verifications=total_verifications,
        total_searches=_metrics["total_searches"],
        active_sessions=0,  # Would track WebSocket sessions
        api_calls_today=_metrics["api_calls_today"],
        api_calls_this_week=_metrics["api_calls_this_week"],
        average_response_time_ms=avg_response_time,
        storage_used_gb=0.0,  # Would calculate from file storage
        uptime_hours=uptime_hours,
        verification_success_rate=verification_success_rate,
        spoof_detection_rate=spoof_rate,
    )


@router.get("/activity", response_model=RecentActivity)
async def get_recent_activity(
    auth: AuthContext = Depends(require_auth),
) -> RecentActivity:
    """Get recent system activity.

    Returns the last 10 operations performed on the system.
    """
    activities = [
        Activity(
            id=a["id"],
            type=a["type"],
            user_id=a.get("user_id"),
            timestamp=a["timestamp"],
            details=a.get("details"),
        )
        for a in _metrics["activities"][:10]
    ]

    return RecentActivity(activities=activities)


# Export functions for other modules to use
__all__ = [
    "record_activity",
    "record_api_call",
    "record_verification",
    "record_search",
    "record_liveness_check",
]
