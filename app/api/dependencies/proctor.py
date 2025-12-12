"""Proctoring API dependencies.

FastAPI dependencies for proctoring endpoints.
Provides dependency injection for use cases and repositories.
"""

import logging
from functools import lru_cache
from typing import Optional

from fastapi import Depends

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
    SessionRateLimiter,
)

# Repository implementations (in-memory for now)
from app.infrastructure.persistence.repositories.memory_proctor_repository import (
    InMemoryProctorSessionRepository,
    InMemoryProctorIncidentRepository,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Proctoring ML Dependencies (Singletons)
# ============================================================================


@lru_cache()
def get_gaze_tracker() -> IGazeTracker:
    """Get gaze tracker instance (singleton)."""
    logger.info("Creating gaze tracker (MediaPipe)")
    return GazeTrackerFactory.create()


@lru_cache()
def get_object_detector() -> IObjectDetector:
    """Get object detector instance (singleton)."""
    logger.info("Creating object detector (YOLO)")
    return ObjectDetectorFactory.create(model_size="nano")


@lru_cache()
def get_deepfake_detector() -> IDeepfakeDetector:
    """Get deepfake detector instance (singleton)."""
    logger.info("Creating deepfake detector (texture-based)")
    return DeepfakeDetectorFactory.create()


@lru_cache()
def get_audio_analyzer() -> IAudioAnalyzer:
    """Get audio analyzer instance (singleton)."""
    logger.info("Creating audio analyzer (basic)")
    return AudioAnalyzerFactory.create()


# ============================================================================
# Proctoring Repository Dependencies (Singletons)
# ============================================================================


@lru_cache()
def get_proctor_session_repository() -> IProctorSessionRepository:
    """Get proctoring session repository (singleton).

    Note: Uses in-memory storage for development.
    Replace with PostgreSQL implementation for production.
    """
    logger.info("Creating proctoring session repository (in-memory)")
    return InMemoryProctorSessionRepository()


@lru_cache()
def get_proctor_incident_repository() -> IProctorIncidentRepository:
    """Get proctoring incident repository (singleton).

    Note: Uses in-memory storage for development.
    Replace with PostgreSQL implementation for production.
    """
    logger.info("Creating proctoring incident repository (in-memory)")
    return InMemoryProctorIncidentRepository()


# ============================================================================
# Proctoring Infrastructure Dependencies
# ============================================================================


@lru_cache()
def get_session_rate_limiter() -> SessionRateLimiter:
    """Get session rate limiter (singleton)."""
    logger.info("Creating session rate limiter (in-memory)")
    return InMemorySessionRateLimiter(
        max_frames_per_second=5,
        max_frames_per_minute=120,
    )


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
    return StartProctorSession(session_repository=session_repo)


def get_submit_frame_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
    gaze_tracker: IGazeTracker = Depends(get_gaze_tracker),
    object_detector: IObjectDetector = Depends(get_object_detector),
    deepfake_detector: IDeepfakeDetector = Depends(get_deepfake_detector),
    audio_analyzer: IAudioAnalyzer = Depends(get_audio_analyzer),
    rate_limiter: SessionRateLimiter = Depends(get_session_rate_limiter),
) -> SubmitFrame:
    """Get submit frame use case with all ML dependencies."""
    # Import face detector and liveness from main container
    from app.core.container import get_face_detector, get_liveness_detector

    return SubmitFrame(
        session_repository=session_repo,
        incident_repository=incident_repo,
        face_detector=get_face_detector(),
        liveness_detector=get_liveness_detector(),
        gaze_tracker=gaze_tracker,
        object_detector=object_detector,
        deepfake_detector=deepfake_detector,
        audio_analyzer=audio_analyzer,
        rate_limiter=rate_limiter,
    )


def get_end_session_use_case(
    session_repo: IProctorSessionRepository = Depends(get_proctor_session_repository),
    incident_repo: IProctorIncidentRepository = Depends(get_proctor_incident_repository),
) -> EndProctorSession:
    """Get end session use case."""
    return EndProctorSession(
        session_repository=session_repo,
        incident_repository=incident_repo,
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
