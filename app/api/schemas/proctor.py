"""Proctoring API schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# Session schemas

class SessionConfigSchema(BaseModel):
    """Session configuration schema."""

    verification_interval_sec: int = Field(60, ge=10, le=300)
    verification_threshold: float = Field(0.6, ge=0.0, le=1.0)
    max_verification_failures: int = Field(3, ge=1, le=10)
    gaze_away_threshold_sec: float = Field(5.0, ge=1.0, le=30.0)
    gaze_sensitivity: float = Field(0.7, ge=0.0, le=1.0)
    enable_object_detection: bool = True
    enable_audio_monitoring: bool = True
    enable_multi_face_detection: bool = True
    enable_deepfake_detection: bool = True
    enable_session_rate_limiting: bool = True
    deepfake_confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    max_frames_per_second: float = Field(2.0, ge=0.5, le=10.0)
    max_frames_per_minute: int = Field(60, ge=10, le=300)
    risk_threshold_warning: float = Field(0.5, ge=0.0, le=1.0)
    risk_threshold_critical: float = Field(0.8, ge=0.0, le=1.0)
    max_pause_duration_sec: int = Field(300, ge=60, le=1800)
    session_timeout_sec: int = Field(14400, ge=3600, le=28800)


class CreateSessionRequest(BaseModel):
    """Request to create a proctoring session."""

    exam_id: str = Field(..., min_length=1, max_length=255)
    user_id: str = Field(..., min_length=1, max_length=255)
    config: Optional[SessionConfigSchema] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateSessionResponse(BaseModel):
    """Response from creating a session."""

    session_id: str
    exam_id: str
    user_id: str
    status: str
    config: Dict[str, Any]


class StartSessionRequest(BaseModel):
    """Request to start a session."""

    baseline_image_base64: Optional[str] = None


class StartSessionResponse(BaseModel):
    """Response from starting a session."""

    session_id: str
    status: str
    started_at: str
    has_baseline: bool


class EndSessionRequest(BaseModel):
    """Request to end a session."""

    reason: Optional[str] = Field(
        None,
        description="Termination reason: normal, user, proctor, identity_failure, "
        "multiple_persons, critical_violation, deepfake, technical, timeout"
    )


class EndSessionResponse(BaseModel):
    """Response from ending a session."""

    session_id: str
    status: str
    ended_at: str
    duration_seconds: float
    termination_reason: Optional[str]
    final_risk_score: float
    total_incidents: int


class SessionResponse(BaseModel):
    """Session details response."""

    id: str
    exam_id: str
    user_id: str
    tenant_id: str
    status: str
    risk_score: float
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    verification_count: int
    verification_failures: int
    incident_count: int
    total_gaze_away_sec: float
    termination_reason: Optional[str]
    duration_seconds: float
    verification_success_rate: float
    config: Dict[str, Any]
    metadata: Dict[str, Any]


class SessionListResponse(BaseModel):
    """List of sessions response."""

    sessions: List[SessionResponse]
    total: int
    limit: int
    offset: int


# Frame submission schemas

class SubmitFrameRequest(BaseModel):
    """Request to submit a frame for analysis."""

    frame_base64: str = Field(..., description="Base64 encoded frame image")
    frame_number: int = Field(..., ge=0)
    audio_base64: Optional[str] = Field(None, description="Base64 encoded audio data")
    audio_sample_rate: int = Field(16000, ge=8000, le=48000)


class FrameAnalysisResponse(BaseModel):
    """Frame analysis result."""

    session_id: str
    frame_number: int
    timestamp: datetime
    face_detected: bool
    face_matched: bool
    face_confidence: float
    face_count: int
    liveness_passed: bool
    liveness_score: float
    gaze: Optional[Dict[str, Any]]
    objects: Optional[Dict[str, Any]]
    audio: Optional[Dict[str, Any]]
    deepfake: Optional[Dict[str, Any]]
    risk_score: float
    has_critical_issues: bool
    processing_time_ms: float


class SubmitFrameResponse(BaseModel):
    """Response from frame submission."""

    session_id: str
    frame_number: int
    risk_score: float
    face_detected: bool
    face_matched: bool
    incidents_created: int
    processing_time_ms: float
    analysis: FrameAnalysisResponse
    rate_limit: Optional[Dict[str, Any]]


# Incident schemas

class CreateIncidentRequest(BaseModel):
    """Request to create an incident."""

    incident_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class CreateIncidentResponse(BaseModel):
    """Response from creating an incident."""

    incident_id: str
    session_id: str
    incident_type: str
    severity: str
    confidence: float
    risk_contribution: float


class ReviewIncidentRequest(BaseModel):
    """Request to review an incident."""

    action: str = Field(
        ...,
        description="Review action: dismissed, acknowledged, warning_issued, "
        "session_paused, session_terminated, escalated"
    )
    notes: Optional[str] = None


class IncidentResponse(BaseModel):
    """Incident details response."""

    id: str
    session_id: str
    incident_type: str
    severity: str
    confidence: float
    timestamp: datetime
    details: Dict[str, Any]
    evidence_count: int
    reviewed: bool
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    review_action: Optional[str]
    review_notes: Optional[str]
    risk_contribution: float


class IncidentListResponse(BaseModel):
    """List of incidents response."""

    incidents: List[IncidentResponse]
    total: int


# Report schemas

class SessionReportResponse(BaseModel):
    """Session report response."""

    session_id: str
    exam_id: str
    user_id: str
    status: str
    duration_seconds: float
    risk_score: float
    verification_count: int
    verification_failures: int
    verification_success_rate: float
    total_incidents: int
    incidents_by_severity: Dict[str, int]
    critical_incidents: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    summary: str


# Rate limit schemas

class RateLimitStatusResponse(BaseModel):
    """Rate limit status response."""

    session_id: str
    frames_last_minute: int
    remaining_this_minute: int
    violation_count: int
    is_throttled: bool
