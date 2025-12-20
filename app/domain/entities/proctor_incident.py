"""Proctoring incident domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class IncidentType(str, Enum):
    """Types of proctoring incidents."""

    # Identity incidents
    FACE_NOT_DETECTED = "face_not_detected"
    FACE_NOT_MATCHED = "face_not_matched"
    MULTIPLE_FACES = "multiple_faces"
    LIVENESS_FAILED = "liveness_failed"
    DEEPFAKE_DETECTED = "deepfake_detected"

    # Attention incidents
    GAZE_AWAY_PROLONGED = "gaze_away_prolonged"
    HEAD_TURNED_AWAY = "head_turned_away"
    USER_LEFT_FRAME = "user_left_frame"

    # Object incidents
    PHONE_DETECTED = "phone_detected"
    BOOK_DETECTED = "book_detected"
    NOTES_DETECTED = "notes_detected"
    ELECTRONIC_DEVICE = "electronic_device"
    UNAUTHORIZED_OBJECT = "unauthorized_object"

    # Audio incidents
    MULTIPLE_VOICES = "multiple_voices"
    SUSPICIOUS_AUDIO = "suspicious_audio"
    VOICE_ASSISTANT = "voice_assistant"

    # Environment incidents
    PERSON_IN_BACKGROUND = "person_in_background"
    SCREEN_SHARE_DETECTED = "screen_share_detected"

    # Technical incidents
    CAMERA_BLOCKED = "camera_blocked"
    CAMERA_SWITCHED = "camera_switched"
    LOW_QUALITY_FEED = "low_quality_feed"

    # Session incidents
    EXCESSIVE_PAUSES = "excessive_pauses"
    SESSION_TIMEOUT = "session_timeout"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class IncidentSeverity(str, Enum):
    """Severity levels for incidents."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewAction(str, Enum):
    """Actions taken after reviewing incident."""

    DISMISSED = "dismissed"
    ACKNOWLEDGED = "acknowledged"
    WARNING_ISSUED = "warning_issued"
    SESSION_PAUSED = "session_paused"
    SESSION_TERMINATED = "session_terminated"
    ESCALATED = "escalated"


# Default severity mapping for incident types
INCIDENT_SEVERITY_MAP: Dict[IncidentType, IncidentSeverity] = {
    # Critical - immediate action
    IncidentType.MULTIPLE_FACES: IncidentSeverity.CRITICAL,
    IncidentType.FACE_NOT_MATCHED: IncidentSeverity.CRITICAL,
    IncidentType.PERSON_IN_BACKGROUND: IncidentSeverity.CRITICAL,
    IncidentType.DEEPFAKE_DETECTED: IncidentSeverity.CRITICAL,

    # High - serious concern
    IncidentType.PHONE_DETECTED: IncidentSeverity.HIGH,
    IncidentType.LIVENESS_FAILED: IncidentSeverity.HIGH,
    IncidentType.MULTIPLE_VOICES: IncidentSeverity.HIGH,
    IncidentType.VOICE_ASSISTANT: IncidentSeverity.HIGH,
    IncidentType.ELECTRONIC_DEVICE: IncidentSeverity.HIGH,

    # Medium - needs review
    IncidentType.BOOK_DETECTED: IncidentSeverity.MEDIUM,
    IncidentType.NOTES_DETECTED: IncidentSeverity.MEDIUM,
    IncidentType.USER_LEFT_FRAME: IncidentSeverity.MEDIUM,
    IncidentType.HEAD_TURNED_AWAY: IncidentSeverity.MEDIUM,
    IncidentType.GAZE_AWAY_PROLONGED: IncidentSeverity.MEDIUM,
    IncidentType.SUSPICIOUS_AUDIO: IncidentSeverity.MEDIUM,
    IncidentType.RATE_LIMIT_EXCEEDED: IncidentSeverity.MEDIUM,

    # Low - informational
    IncidentType.FACE_NOT_DETECTED: IncidentSeverity.LOW,
    IncidentType.CAMERA_BLOCKED: IncidentSeverity.LOW,
    IncidentType.LOW_QUALITY_FEED: IncidentSeverity.LOW,
    IncidentType.EXCESSIVE_PAUSES: IncidentSeverity.LOW,
}


def get_default_severity(incident_type: IncidentType) -> IncidentSeverity:
    """Get default severity for incident type."""
    return INCIDENT_SEVERITY_MAP.get(incident_type, IncidentSeverity.MEDIUM)


@dataclass
class IncidentEvidence:
    """Evidence attached to an incident."""

    id: UUID
    incident_id: UUID
    evidence_type: str  # "image", "video_clip", "audio_clip", "screenshot"
    storage_url: str
    thumbnail_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        incident_id: UUID,
        evidence_type: str,
        storage_url: str,
        thumbnail_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "IncidentEvidence":
        """Factory method to create evidence."""
        return cls(
            id=uuid4(),
            incident_id=incident_id,
            evidence_type=evidence_type,
            storage_url=storage_url,
            thumbnail_url=thumbnail_url,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "incident_id": str(self.incident_id),
            "evidence_type": self.evidence_type,
            "storage_url": self.storage_url,
            "thumbnail_url": self.thumbnail_url,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ProctorIncident:
    """Proctoring incident entity."""

    id: UUID
    session_id: UUID
    incident_type: IncidentType
    severity: IncidentSeverity
    confidence: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    evidence: List[IncidentEvidence] = field(default_factory=list)
    reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_action: Optional[ReviewAction] = None
    review_notes: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate incident data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0-1, got {self.confidence}")

    @classmethod
    def create(
        cls,
        session_id: UUID,
        incident_type: IncidentType,
        confidence: float,
        severity: Optional[IncidentSeverity] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ProctorIncident":
        """Factory method to create incident."""
        return cls(
            id=uuid4(),
            session_id=session_id,
            incident_type=incident_type,
            severity=severity or get_default_severity(incident_type),
            confidence=confidence,
            timestamp=datetime.utcnow(),
            details=details or {},
        )

    def add_evidence(self, evidence: IncidentEvidence) -> None:
        """Add evidence to incident."""
        self.evidence.append(evidence)

    def mark_reviewed(
        self,
        reviewer: str,
        action: ReviewAction,
        notes: Optional[str] = None,
    ) -> None:
        """Mark incident as reviewed."""
        self.reviewed = True
        self.reviewed_at = datetime.utcnow()
        self.reviewed_by = reviewer
        self.review_action = action
        self.review_notes = notes

    def get_risk_contribution(self) -> float:
        """Calculate risk contribution based on severity and confidence."""
        severity_weights = {
            IncidentSeverity.LOW: 0.1,
            IncidentSeverity.MEDIUM: 0.3,
            IncidentSeverity.HIGH: 0.6,
            IncidentSeverity.CRITICAL: 1.0,
        }

        base_weight = severity_weights.get(self.severity, 0.1)
        return base_weight * self.confidence

    def is_critical(self) -> bool:
        """Check if incident is critical severity."""
        return self.severity == IncidentSeverity.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "evidence_count": len(self.evidence),
            "evidence": [e.to_dict() for e in self.evidence],
            "reviewed": self.reviewed,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "review_action": self.review_action.value if self.review_action else None,
            "review_notes": self.review_notes,
            "risk_contribution": self.get_risk_contribution(),
        }
