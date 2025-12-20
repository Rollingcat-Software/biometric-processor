"""Proctoring session domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import numpy as np


class SessionStatus(str, Enum):
    """Proctor session status states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    FLAGGED = "flagged"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    EXPIRED = "expired"


class TerminationReason(str, Enum):
    """Reasons for session termination."""

    NORMAL_COMPLETION = "normal_completion"
    USER_ENDED = "user_ended"
    PROCTOR_ENDED = "proctor_ended"
    IDENTITY_FAILURE = "identity_failure"
    MULTIPLE_PERSONS = "multiple_persons"
    CRITICAL_VIOLATION = "critical_violation"
    DEEPFAKE_DETECTED = "deepfake_detected"
    TECHNICAL_FAILURE = "technical_failure"
    TIMEOUT = "timeout"


@dataclass
class SessionConfig:
    """Configuration for proctoring session behavior."""

    # Verification settings
    verification_interval_sec: int = 60
    verification_threshold: float = 0.6
    max_verification_failures: int = 3

    # Gaze tracking settings
    gaze_away_threshold_sec: float = 5.0
    gaze_sensitivity: float = 0.7

    # Detection toggles
    enable_object_detection: bool = True
    enable_audio_monitoring: bool = True
    enable_multi_face_detection: bool = True
    enable_deepfake_detection: bool = True
    enable_session_rate_limiting: bool = True

    # Deepfake detection
    deepfake_confidence_threshold: float = 0.7

    # Rate limiting
    max_frames_per_second: float = 2.0
    max_frames_per_minute: int = 60

    # Risk thresholds
    risk_threshold_warning: float = 0.5
    risk_threshold_critical: float = 0.8

    # Session limits
    max_pause_duration_sec: int = 300
    session_timeout_sec: int = 14400

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "verification_interval_sec": self.verification_interval_sec,
            "verification_threshold": self.verification_threshold,
            "max_verification_failures": self.max_verification_failures,
            "gaze_away_threshold_sec": self.gaze_away_threshold_sec,
            "gaze_sensitivity": self.gaze_sensitivity,
            "enable_object_detection": self.enable_object_detection,
            "enable_audio_monitoring": self.enable_audio_monitoring,
            "enable_multi_face_detection": self.enable_multi_face_detection,
            "enable_deepfake_detection": self.enable_deepfake_detection,
            "enable_session_rate_limiting": self.enable_session_rate_limiting,
            "deepfake_confidence_threshold": self.deepfake_confidence_threshold,
            "max_frames_per_second": self.max_frames_per_second,
            "max_frames_per_minute": self.max_frames_per_minute,
            "risk_threshold_warning": self.risk_threshold_warning,
            "risk_threshold_critical": self.risk_threshold_critical,
            "max_pause_duration_sec": self.max_pause_duration_sec,
            "session_timeout_sec": self.session_timeout_sec,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionConfig":
        """Create from dictionary."""
        return cls(
            verification_interval_sec=data.get("verification_interval_sec", 60),
            verification_threshold=data.get("verification_threshold", 0.6),
            max_verification_failures=data.get("max_verification_failures", 3),
            gaze_away_threshold_sec=data.get("gaze_away_threshold_sec", 5.0),
            gaze_sensitivity=data.get("gaze_sensitivity", 0.7),
            enable_object_detection=data.get("enable_object_detection", True),
            enable_audio_monitoring=data.get("enable_audio_monitoring", True),
            enable_multi_face_detection=data.get("enable_multi_face_detection", True),
            enable_deepfake_detection=data.get("enable_deepfake_detection", True),
            enable_session_rate_limiting=data.get("enable_session_rate_limiting", True),
            deepfake_confidence_threshold=data.get("deepfake_confidence_threshold", 0.7),
            max_frames_per_second=data.get("max_frames_per_second", 2.0),
            max_frames_per_minute=data.get("max_frames_per_minute", 60),
            risk_threshold_warning=data.get("risk_threshold_warning", 0.5),
            risk_threshold_critical=data.get("risk_threshold_critical", 0.8),
            max_pause_duration_sec=data.get("max_pause_duration_sec", 300),
            session_timeout_sec=data.get("session_timeout_sec", 14400),
        )


@dataclass
class ProctorSession:
    """Proctoring session entity."""

    id: UUID
    exam_id: str
    user_id: str
    tenant_id: str
    config: SessionConfig
    status: SessionStatus = SessionStatus.CREATED
    risk_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    baseline_embedding: Optional[np.ndarray] = None
    verification_count: int = 0
    verification_failures: int = 0
    incident_count: int = 0
    total_gaze_away_sec: float = 0.0
    termination_reason: Optional[TerminationReason] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate session data."""
        if not self.exam_id:
            raise ValueError("exam_id is required")
        if not self.user_id:
            raise ValueError("user_id is required")
        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError(f"risk_score must be 0-1, got {self.risk_score}")

    @classmethod
    def create(
        cls,
        exam_id: str,
        user_id: str,
        tenant_id: str,
        config: Optional[SessionConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ProctorSession":
        """Factory method to create a new session."""
        return cls(
            id=uuid4(),
            exam_id=exam_id,
            user_id=user_id,
            tenant_id=tenant_id,
            config=config or SessionConfig(),
            metadata=metadata or {},
        )

    def can_start(self) -> bool:
        """Check if session can be started."""
        return self.status == SessionStatus.CREATED

    def can_pause(self) -> bool:
        """Check if session can be paused."""
        return self.status == SessionStatus.ACTIVE

    def can_resume(self) -> bool:
        """Check if session can be resumed."""
        return self.status == SessionStatus.PAUSED

    def can_end(self) -> bool:
        """Check if session can be ended normally."""
        return self.status in (
            SessionStatus.ACTIVE,
            SessionStatus.PAUSED,
            SessionStatus.FLAGGED,
        )

    def is_active(self) -> bool:
        """Check if session is actively monitoring."""
        return self.status == SessionStatus.ACTIVE

    def is_terminal(self) -> bool:
        """Check if session is in terminal state."""
        return self.status in (
            SessionStatus.COMPLETED,
            SessionStatus.TERMINATED,
            SessionStatus.EXPIRED,
        )

    def start(self, baseline_embedding: np.ndarray) -> None:
        """Start the proctoring session."""
        if not self.can_start():
            raise ValueError(f"Cannot start session in status: {self.status}")

        self.status = SessionStatus.ACTIVE
        self.started_at = datetime.utcnow()
        self.baseline_embedding = baseline_embedding

    def pause(self) -> None:
        """Pause the session."""
        if not self.can_pause():
            raise ValueError(f"Cannot pause session in status: {self.status}")

        self.status = SessionStatus.PAUSED
        self.paused_at = datetime.utcnow()

    def resume(self) -> None:
        """Resume a paused session."""
        if not self.can_resume():
            raise ValueError(f"Cannot resume session in status: {self.status}")

        self.status = SessionStatus.ACTIVE
        self.paused_at = None

    def complete(self) -> None:
        """Complete the session normally."""
        if not self.can_end():
            raise ValueError(f"Cannot complete session in status: {self.status}")

        self.status = SessionStatus.COMPLETED
        self.ended_at = datetime.utcnow()
        self.termination_reason = TerminationReason.NORMAL_COMPLETION

    def terminate(self, reason: TerminationReason) -> None:
        """Terminate the session with reason."""
        if self.is_terminal():
            return

        self.status = SessionStatus.TERMINATED
        self.ended_at = datetime.utcnow()
        self.termination_reason = reason

    def flag(self) -> None:
        """Flag session as high risk."""
        if self.status == SessionStatus.ACTIVE:
            self.status = SessionStatus.FLAGGED

    def update_risk_score(self, score: float) -> None:
        """Update the aggregated risk score."""
        self.risk_score = max(0.0, min(1.0, score))

        if self.risk_score >= self.config.risk_threshold_critical:
            self.flag()

    def record_verification(self, success: bool) -> None:
        """Record a verification attempt."""
        self.verification_count += 1
        if not success:
            self.verification_failures += 1

    def record_incident(self) -> None:
        """Increment incident count."""
        self.incident_count += 1

    def add_gaze_away_time(self, seconds: float) -> None:
        """Add time spent looking away."""
        self.total_gaze_away_sec += seconds

    def get_duration_seconds(self) -> float:
        """Get session duration in seconds."""
        if not self.started_at:
            return 0.0

        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def get_verification_success_rate(self) -> float:
        """Get verification success rate."""
        if self.verification_count == 0:
            return 1.0

        successes = self.verification_count - self.verification_failures
        return successes / self.verification_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "exam_id": self.exam_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "risk_score": self.risk_score,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "verification_count": self.verification_count,
            "verification_failures": self.verification_failures,
            "incident_count": self.incident_count,
            "total_gaze_away_sec": self.total_gaze_away_sec,
            "termination_reason": self.termination_reason.value if self.termination_reason else None,
            "duration_seconds": self.get_duration_seconds(),
            "verification_success_rate": self.get_verification_success_rate(),
            "config": self.config.to_dict(),
            "metadata": self.metadata,
        }
