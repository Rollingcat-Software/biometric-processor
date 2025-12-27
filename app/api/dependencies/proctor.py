"""Proctoring API dependencies.

FastAPI dependencies for proctoring endpoints.
Provides dependency injection for use cases and repositories.
All settings are loaded from environment configuration.
"""

import logging
from functools import lru_cache
from typing import Optional

from fastapi import Depends

from app.core.config import settings
from app.domain.interfaces.audio_analyzer import IAudioAnalyzer
from app.domain.interfaces.deepfake_detector import IDeepfakeDetector
from app.domain.interfaces.gaze_tracker import IGazeTracker
from app.domain.interfaces.object_detector import IObjectDetector
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

# Use cases
from app.application.use_cases.proctor.create_session import CreateProctorSession
from app.application.use_cases.proctor.start_session import StartProctorSession
from app.application.use_cases.proctor.submit_frame import SubmitFrame
from app.application.use_cases.proctor.end_session import (
    EndProctorSession,
    PauseProctorSession,
    ResumeProctorSession,
)
from app.application.use_cases.proctor.create_incident import CreateIncident, ReviewIncident
from app.application.use_cases.proctor.get_session_report import (
    GetSessionReport,
    ListSessionIncidents,
)

# ML implementations
from app.infrastructure.ml.proctoring.factories import (
    GazeTrackerFactory,
    ObjectDetectorFactory,
    DeepfakeDetectorFactory,
    AudioAnalyzerFactory,
)

# Resilience
from app.infrastructure.resilience.session_rate_limiter import (
    InMemorySessionRateLimiter,
    SessionRateLimitConfig,
    SessionRateLimiter,
)

# Repository implementations
from app.infrastructure.persistence.repositories.postgres_session_repository import (
    PostgresSessionRepository,
)
from app.infrastructure.persistence.repositories.postgres_incident_repository import (
    PostgresIncidentRepository,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Proctoring ML Dependencies (Singletons)
# Uses configuration from settings
# ============================================================================


@lru_cache()
def get_gaze_tracker() -> IGazeTracker:
    """Get gaze tracker instance (singleton).

    Configuration from:
    - PROCTOR_GAZE_THRESHOLD
    - PROCTOR_HEAD_PITCH_THRESHOLD
    - PROCTOR_HEAD_YAW_THRESHOLD
    """
    if not settings.PROCTOR_GAZE_ENABLED:
        logger.info("Gaze tracking disabled, returning None")
        return None

    logger.info(
        f"Creating gaze tracker (MediaPipe) with threshold={settings.PROCTOR_GAZE_THRESHOLD}"
    )
    return GazeTrackerFactory.create(
        gaze_threshold=settings.PROCTOR_GAZE_THRESHOLD,
        head_pose_threshold=(
            settings.PROCTOR_HEAD_PITCH_THRESHOLD,
            settings.PROCTOR_HEAD_YAW_THRESHOLD,
        ),
    )


@lru_cache()
def get_object_detector() -> IObjectDetector:
    """Get object detector instance (singleton).

    Configuration from:
    - PROCTOR_OBJECT_MODEL_SIZE
    - PROCTOR_OBJECT_CONFIDENCE_THRESHOLD
    - PROCTOR_MAX_PERSONS_ALLOWED
    """
    if not settings.PROCTOR_OBJECT_DETECTION_ENABLED:
        logger.info("Object detection disabled, returning None")
        return None

    logger.info(
        f"Creating object detector (YOLO {settings.PROCTOR_OBJECT_MODEL_SIZE}) "
        f"with threshold={settings.PROCTOR_OBJECT_CONFIDENCE_THRESHOLD}"
    )
    return ObjectDetectorFactory.create(
        model_size=settings.PROCTOR_OBJECT_MODEL_SIZE,
        confidence_threshold=settings.PROCTOR_OBJECT_CONFIDENCE_THRESHOLD,
        max_persons_allowed=settings.PROCTOR_MAX_PERSONS_ALLOWED,
    )


@lru_cache()
def get_deepfake_detector() -> IDeepfakeDetector:
    """Get deepfake detector instance (singleton).

    Configuration from:
    - PROCTOR_DEEPFAKE_THRESHOLD
    - PROCTOR_DEEPFAKE_TEMPORAL_WINDOW
    """
    if not settings.PROCTOR_DEEPFAKE_ENABLED:
        logger.info("Deepfake detection disabled, returning None")
        return None

    logger.info(
        f"Creating deepfake detector (texture-based) "
        f"with threshold={settings.PROCTOR_DEEPFAKE_THRESHOLD}"
    )
    return DeepfakeDetectorFactory.create(
        deepfake_threshold=settings.PROCTOR_DEEPFAKE_THRESHOLD,
        temporal_window=settings.PROCTOR_DEEPFAKE_TEMPORAL_WINDOW,
    )


@lru_cache()
def get_audio_analyzer() -> IAudioAnalyzer:
    """Get audio analyzer instance (singleton).

    Configuration from:
    - PROCTOR_AUDIO_SAMPLE_RATE
    - PROCTOR_AUDIO_VAD_THRESHOLD
    """
    if not settings.PROCTOR_AUDIO_ENABLED:
        logger.info("Audio analysis disabled, returning None")
        return None

    logger.info(
        f"Creating audio analyzer (basic) "
        f"with sample_rate={settings.PROCTOR_AUDIO_SAMPLE_RATE}"
    )
    return AudioAnalyzerFactory.create(
        sample_rate=settings.PROCTOR_AUDIO_SAMPLE_RATE,
        vad_threshold=settings.PROCTOR_AUDIO_VAD_THRESHOLD,
    )


# ============================================================================
# Proctoring Repository Dependencies (Singletons)
# ============================================================================

# Database pool for PostgreSQL (initialized lazily)
_db_pool = None


async def _get_db_pool():
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None and settings.DATABASE_URL:
        import asyncpg
        _db_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=settings.DATABASE_POOL_SIZE,
        )
        logger.info("Created PostgreSQL connection pool for proctoring")
    return _db_pool


@lru_cache()
def get_proctor_session_repository() -> IProctorSessionRepository:
    """Get proctoring session repository (singleton).

    Storage type controlled by PROCTOR_STORAGE_TYPE:
    - "memory": In-memory storage (development/testing)
    - "postgres": PostgreSQL storage (production)
    """
    storage_type = settings.PROCTOR_STORAGE_TYPE

    if storage_type == "postgres" and settings.DATABASE_URL:
        logger.info("Creating proctoring session repository (PostgreSQL)")
        return PostgresSessionRepository(database_url=settings.DATABASE_URL)
    else:
        raise ValueError(
            "PROCTOR_STORAGE_TYPE must be 'postgres' and DATABASE_URL must be configured. "
            "In-memory repositories have been removed for production safety."
        )


@lru_cache()
def get_proctor_incident_repository() -> IProctorIncidentRepository:
    """Get proctoring incident repository (singleton).

    Storage type controlled by PROCTOR_STORAGE_TYPE:
    - "memory": In-memory storage (development/testing)
    - "postgres": PostgreSQL storage (production)
    """
    storage_type = settings.PROCTOR_STORAGE_TYPE

    if storage_type == "postgres" and settings.DATABASE_URL:
        logger.info("Creating proctoring incident repository (PostgreSQL)")
        return PostgresIncidentRepository(database_url=settings.DATABASE_URL)
    else:
        raise ValueError(
            "PROCTOR_STORAGE_TYPE must be 'postgres' and DATABASE_URL must be configured. "
            "In-memory repositories have been removed for production safety."
        )


# ============================================================================
# Proctoring Infrastructure Dependencies
# ============================================================================


@lru_cache()
def get_session_rate_limiter() -> Optional[SessionRateLimiter]:
    """Get session rate limiter (singleton).

    Configuration from:
    - PROCTOR_RATE_LIMIT_ENABLED
    - PROCTOR_MAX_FRAMES_PER_SECOND
    - PROCTOR_MAX_FRAMES_PER_MINUTE
    - PROCTOR_RATE_LIMIT_BURST_ALLOWANCE
    """
    if not settings.PROCTOR_RATE_LIMIT_ENABLED:
        logger.info("Per-session rate limiting disabled")
        return None

    logger.info(
        f"Creating session rate limiter: "
        f"{settings.PROCTOR_MAX_FRAMES_PER_SECOND}/sec, "
        f"{settings.PROCTOR_MAX_FRAMES_PER_MINUTE}/min"
    )
    return InMemorySessionRateLimiter(config=SessionRateLimitConfig(
        max_frames_per_second=settings.PROCTOR_MAX_FRAMES_PER_SECOND,
        max_frames_per_minute=settings.PROCTOR_MAX_FRAMES_PER_MINUTE,
        burst_allowance=settings.PROCTOR_RATE_LIMIT_BURST_ALLOWANCE))


# ============================================================================
# Proctoring Use Case Dependencies
# ============================================================================


def get_create_session_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
) -> CreateProctorSession:
    """Get create session use case."""
    return CreateProctorSession(session_repository=session_repo)


def get_start_session_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
) -> StartProctorSession:
    """Get start session use case."""
    # Import embedding dependencies from main container
    from app.core.container import get_embedding_repository, get_embedding_extractor

    return StartProctorSession(
        session_repository=session_repo,
        embedding_repository=get_embedding_repository(),
        embedding_extractor=get_embedding_extractor(),
    )


def get_submit_frame_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
    gaze_tracker: Optional[IGazeTracker] = Depends(get_gaze_tracker),
    object_detector: Optional[IObjectDetector] = Depends(get_object_detector),
    deepfake_detector: Optional[IDeepfakeDetector] = Depends(get_deepfake_detector),
    audio_analyzer: Optional[IAudioAnalyzer] = Depends(get_audio_analyzer),
    rate_limiter: Optional[SessionRateLimiter] = Depends(get_session_rate_limiter),
) -> SubmitFrame:
    """Get submit frame use case with all ML dependencies.

    Note: Some dependencies may be None if disabled in configuration.
    """
    # Import face detector, liveness, embedding extractor and similarity calculator from main container
    from app.core.container import (
        get_face_detector,
        get_liveness_detector,
        get_embedding_extractor,
        get_similarity_calculator,
    )

    return SubmitFrame(
        session_repository=session_repo,
        incident_repository=incident_repo,
        face_verifier=get_face_detector(),
        liveness_detector=get_liveness_detector(),
        embedding_extractor=get_embedding_extractor(),
        similarity_calculator=get_similarity_calculator(),
        gaze_tracker=gaze_tracker,
        object_detector=object_detector,
        deepfake_detector=deepfake_detector,
        audio_analyzer=audio_analyzer,
        rate_limiter=rate_limiter,
    )


def get_end_session_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
) -> EndProctorSession:
    """Get end session use case."""
    return EndProctorSession(
        session_repository=session_repo,
    )


def get_pause_session_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
) -> PauseProctorSession:
    """Get pause session use case."""
    return PauseProctorSession(session_repository=session_repo)


def get_resume_session_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
) -> ResumeProctorSession:
    """Get resume session use case."""
    return ResumeProctorSession(session_repository=session_repo)


def get_create_incident_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
) -> CreateIncident:
    """Get create incident use case."""
    return CreateIncident(
        session_repository=session_repo,
        incident_repository=incident_repo,
    )


def get_review_incident_use_case(
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
) -> ReviewIncident:
    """Get review incident use case."""
    return ReviewIncident(incident_repository=incident_repo)


def get_session_report_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
) -> GetSessionReport:
    """Get session report use case."""
    return GetSessionReport(
        session_repository=session_repo,
        incident_repository=incident_repo,
    )


def get_list_incidents_use_case(
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
) -> ListSessionIncidents:
    """Get list incidents use case."""
    return ListSessionIncidents(incident_repository=incident_repo)


# ============================================================================
# Cache Clear Utility
# ============================================================================


def clear_proctor_cache() -> None:
    """Clear proctoring dependency cache (for testing)."""
    logger.warning("Clearing proctoring dependency cache")

    get_gaze_tracker.cache_clear()
    get_object_detector.cache_clear()
    get_deepfake_detector.cache_clear()
    get_audio_analyzer.cache_clear()
    get_proctor_session_repository.cache_clear()
    get_proctor_incident_repository.cache_clear()
    get_session_rate_limiter.cache_clear()


# ============================================================================
# Configuration Summary
# ============================================================================


def get_proctor_config_summary() -> dict:
    """Get summary of proctoring configuration for debugging."""
    return {
        "enabled": settings.PROCTOR_ENABLED,
        "storage_type": settings.PROCTOR_STORAGE_TYPE,
        "features": {
            "gaze_tracking": settings.PROCTOR_GAZE_ENABLED,
            "object_detection": settings.PROCTOR_OBJECT_DETECTION_ENABLED,
            "deepfake_detection": settings.PROCTOR_DEEPFAKE_ENABLED,
            "audio_analysis": settings.PROCTOR_AUDIO_ENABLED,
        },
        "thresholds": {
            "verification": settings.PROCTOR_VERIFICATION_THRESHOLD,
            "liveness": settings.PROCTOR_LIVENESS_THRESHOLD,
            "gaze": settings.PROCTOR_GAZE_THRESHOLD,
            "deepfake": settings.PROCTOR_DEEPFAKE_THRESHOLD,
            "risk_warning": settings.PROCTOR_RISK_THRESHOLD_WARNING,
            "risk_critical": settings.PROCTOR_RISK_THRESHOLD_CRITICAL,
        },
        "rate_limiting": {
            "enabled": settings.PROCTOR_RATE_LIMIT_ENABLED,
            "max_frames_per_second": settings.PROCTOR_MAX_FRAMES_PER_SECOND,
            "max_frames_per_minute": settings.PROCTOR_MAX_FRAMES_PER_MINUTE,
        },
        "circuit_breaker": {
            "enabled": settings.PROCTOR_CIRCUIT_BREAKER_ENABLED,
            "failure_threshold": settings.PROCTOR_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            "timeout_sec": settings.PROCTOR_CIRCUIT_BREAKER_TIMEOUT_SEC,
        },
    }
