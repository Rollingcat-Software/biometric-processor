"""API dependencies for dependency injection."""

from app.api.dependencies.proctor import (
    get_gaze_tracker,
    get_object_detector,
    get_deepfake_detector,
    get_audio_analyzer,
    get_proctor_session_repository,
    get_proctor_incident_repository,
    get_session_rate_limiter,
    get_create_session_use_case,
    get_start_session_use_case,
    get_submit_frame_use_case,
    get_end_session_use_case,
    get_pause_session_use_case,
    get_resume_session_use_case,
    get_create_incident_use_case,
    get_review_incident_use_case,
    get_session_report_use_case,
    get_list_incidents_use_case,
    clear_proctor_cache,
)

__all__ = [
    # ML components
    "get_gaze_tracker",
    "get_object_detector",
    "get_deepfake_detector",
    "get_audio_analyzer",
    # Repositories
    "get_proctor_session_repository",
    "get_proctor_incident_repository",
    # Infrastructure
    "get_session_rate_limiter",
    # Use cases
    "get_create_session_use_case",
    "get_start_session_use_case",
    "get_submit_frame_use_case",
    "get_end_session_use_case",
    "get_pause_session_use_case",
    "get_resume_session_use_case",
    "get_create_incident_use_case",
    "get_review_incident_use_case",
    "get_session_report_use_case",
    "get_list_incidents_use_case",
    # Utilities
    "clear_proctor_cache",
]
