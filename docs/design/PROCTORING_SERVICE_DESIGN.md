# Proctoring Service - Technical Design Document

**Version:** 1.0
**Date:** December 2024
**Status:** PROPOSED
**Author:** Architecture Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Domain Model](#3-domain-model)
4. [Use Cases](#4-use-cases)
5. [API Specification](#5-api-specification)
6. [Infrastructure Components](#6-infrastructure-components)
7. [Data Flow](#7-data-flow)
8. [Configuration](#8-configuration)
9. [Security & Privacy](#9-security--privacy)
10. [Monitoring & Observability](#10-monitoring--observability)
11. [Implementation Phases](#11-implementation-phases)
12. [Validation Checklist](#12-validation-checklist)

---

## 1. Overview

### 1.1 Purpose

Design a continuous identity verification and proctoring service that monitors exam-takers in real-time, detects suspicious behavior, and ensures exam integrity through multi-modal analysis.

### 1.2 Goals

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **Continuous Identity** | Verify user remains the same throughout session | >99% true positive rate |
| **Cheating Detection** | Detect unauthorized materials, persons, behaviors | <5% false positive rate |
| **Real-time Alerts** | Notify on suspicious activity immediately | <2s alert latency |
| **Scalability** | Handle concurrent proctoring sessions | 10,000+ concurrent sessions |
| **Privacy Compliance** | Meet GDPR/CCPA requirements | Full compliance |

### 1.3 Non-Goals (Out of Scope for MVP)

- Browser lockdown (client-side responsibility)
- Live human proctor interface
- Secondary camera (360°) support
- Keystroke/mouse behavioral biometrics

### 1.4 Design Principles

1. **Clean Architecture** - Domain logic independent of frameworks
2. **SOLID Principles** - Single responsibility, open for extension
3. **Event-Driven** - Decouple components via events/webhooks
4. **Privacy-First** - Minimize data collection, maximize transparency
5. **Fail-Safe** - Graceful degradation, no false terminations

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │   Webcam    │  │ Microphone  │  │   Screen    │  │ Exam Platform │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬───────┘  │
│         │                │                │                  │          │
│         └────────────────┴────────────────┴──────────────────┘          │
│                                   │                                      │
│                          Frame Capture SDK                               │
└───────────────────────────────────┼──────────────────────────────────────┘
                                    │ HTTPS/WebSocket
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  API Key     │  │    Rate      │  │   Request    │  │   Routing    │  │
│  │  Auth        │  │   Limiting   │  │  Validation  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────────────────┼───────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼───────────────────────────────────────┐
│                        PROCTORING SERVICE                                  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      SESSION MANAGER                                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │  │
│  │  │ Create  │  │  Start  │  │ Monitor │  │  Pause  │  │   End   │   │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│  ┌─────────────────────────────────┼───────────────────────────────────┐  │
│  │                    ANALYSIS PIPELINE                                 │  │
│  │                                                                      │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │
│  │  │   Face     │  │    Gaze    │  │   Object   │  │   Audio    │    │  │
│  │  │ Verifier   │  │  Tracker   │  │  Detector  │  │  Analyzer  │    │  │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │  │
│  │        │               │               │               │           │  │
│  │        └───────────────┴───────────────┴───────────────┘           │  │
│  │                               │                                     │  │
│  │                    ┌──────────┴──────────┐                         │  │
│  │                    │   FUSION ENGINE     │                         │  │
│  │                    │  (Risk Aggregator)  │                         │  │
│  │                    └──────────┬──────────┘                         │  │
│  └───────────────────────────────┼─────────────────────────────────────┘  │
│                                  │                                         │
│  ┌───────────────────────────────┼─────────────────────────────────────┐  │
│  │                    INCIDENT MANAGER                                  │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │  │
│  │  │ Create  │  │ Classify│  │ Score   │  │Evidence │  │ Notify  │   │  │
│  │  │Incident │  │Severity │  │  Risk   │  │ Capture │  │(Webhook)│   │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┼───────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼───────────────────────────────────────┐
│                           DATA LAYER                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  PostgreSQL  │  │    Redis     │  │     S3       │  │  TimeSeries  │  │
│  │  (Sessions,  │  │   (Cache,    │  │  (Evidence   │  │  (Metrics,   │  │
│  │  Incidents)  │  │   State)     │  │   Storage)   │  │   Events)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| **Session Manager** | Lifecycle management, state machine | Python/FastAPI |
| **Face Verifier** | Continuous identity verification | DeepFace, existing code |
| **Gaze Tracker** | Head pose & eye direction monitoring | MediaPipe |
| **Object Detector** | Phone/book/person detection | YOLOv8 |
| **Audio Analyzer** | Voice activity, multiple speakers | WebRTC VAD |
| **Fusion Engine** | Aggregate signals, compute risk | Custom Python |
| **Incident Manager** | Flag, classify, store incidents | Python |

---

## 3. Domain Model

### 3.1 Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────┐
│   ProctorSession    │       │    SessionConfig    │
├─────────────────────┤       ├─────────────────────┤
│ id: UUID            │──────▶│ id: UUID            │
│ exam_id: str        │       │ verification_interval│
│ user_id: str        │       │ gaze_threshold      │
│ tenant_id: str      │       │ object_detection    │
│ config_id: UUID     │       │ audio_monitoring    │
│ status: SessionStatus│       │ risk_thresholds     │
│ risk_score: float   │       └─────────────────────┘
│ started_at: datetime│
│ ended_at: datetime  │       ┌─────────────────────┐
│ baseline_embedding  │──────▶│   FaceEmbedding     │
└─────────┬───────────┘       │   (existing)        │
          │                   └─────────────────────┘
          │ 1:N
          ▼
┌─────────────────────┐       ┌─────────────────────┐
│  ProctorIncident    │       │   IncidentEvidence  │
├─────────────────────┤       ├─────────────────────┤
│ id: UUID            │──────▶│ id: UUID            │
│ session_id: UUID    │       │ incident_id: UUID   │
│ type: IncidentType  │       │ type: EvidenceType  │
│ severity: Severity  │       │ storage_url: str    │
│ confidence: float   │       │ metadata: dict      │
│ timestamp: datetime │       │ created_at: datetime│
│ details: dict       │       └─────────────────────┘
│ reviewed: bool      │
│ reviewer_action: str│
└─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│ VerificationEvent   │       │   GazeEvent         │
├─────────────────────┤       ├─────────────────────┤
│ id: UUID            │       │ id: UUID            │
│ session_id: UUID    │       │ session_id: UUID    │
│ timestamp: datetime │       │ timestamp: datetime │
│ face_detected: bool │       │ head_pose: HeadPose │
│ face_matched: bool  │       │ gaze_direction: Vec │
│ confidence: float   │       │ on_screen: bool     │
│ liveness_score: float│      │ duration_off: float │
│ quality_score: float│       └─────────────────────┘
└─────────────────────┘
```

### 3.2 Domain Entities

#### 3.2.1 ProctorSession

```python
# app/domain/entities/proctor_session.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import numpy as np


class SessionStatus(str, Enum):
    """Proctor session status states."""

    CREATED = "created"          # Session created, not started
    INITIALIZING = "initializing" # Initial verification in progress
    ACTIVE = "active"            # Session running, monitoring active
    PAUSED = "paused"            # Temporarily paused (bathroom, etc.)
    FLAGGED = "flagged"          # High risk, requires attention
    COMPLETED = "completed"      # Normal completion
    TERMINATED = "terminated"    # Forcibly ended (cheating detected)
    EXPIRED = "expired"          # Session timed out


class TerminationReason(str, Enum):
    """Reasons for session termination."""

    NORMAL_COMPLETION = "normal_completion"
    USER_ENDED = "user_ended"
    PROCTOR_ENDED = "proctor_ended"
    IDENTITY_FAILURE = "identity_failure"
    MULTIPLE_PERSONS = "multiple_persons"
    CRITICAL_VIOLATION = "critical_violation"
    TECHNICAL_FAILURE = "technical_failure"
    TIMEOUT = "timeout"


@dataclass
class SessionConfig:
    """Configuration for proctoring session behavior.

    Attributes:
        verification_interval_sec: Seconds between face verifications
        verification_threshold: Minimum confidence for successful verification
        max_verification_failures: Failures before flagging
        gaze_away_threshold_sec: Seconds looking away before incident
        gaze_sensitivity: Sensitivity of gaze detection (0.0-1.0)
        enable_object_detection: Whether to detect phones/books
        enable_audio_monitoring: Whether to analyze audio
        enable_multi_face_detection: Whether to detect additional persons
        risk_threshold_warning: Risk score threshold for warning
        risk_threshold_critical: Risk score threshold for critical
        max_pause_duration_sec: Maximum allowed pause duration
        session_timeout_sec: Maximum session duration
    """

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

    # Risk thresholds
    risk_threshold_warning: float = 0.5
    risk_threshold_critical: float = 0.8

    # Session limits
    max_pause_duration_sec: int = 300  # 5 minutes
    session_timeout_sec: int = 14400   # 4 hours

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
            "risk_threshold_warning": self.risk_threshold_warning,
            "risk_threshold_critical": self.risk_threshold_critical,
            "max_pause_duration_sec": self.max_pause_duration_sec,
            "session_timeout_sec": self.session_timeout_sec,
        }


@dataclass
class ProctorSession:
    """Proctoring session entity.

    Represents a single proctored exam session with all associated
    state and metrics. Follows the Entity pattern from DDD.

    Attributes:
        id: Unique session identifier
        exam_id: External exam/assessment identifier
        user_id: User being proctored
        tenant_id: Multi-tenancy identifier
        config: Session configuration
        status: Current session status
        risk_score: Aggregated risk score (0.0-1.0)
        created_at: Session creation timestamp
        started_at: When monitoring actually started
        ended_at: When session ended
        baseline_embedding: Reference face embedding for verification
        verification_count: Total verifications performed
        verification_failures: Count of failed verifications
        incident_count: Total incidents recorded
        total_gaze_away_sec: Cumulative time looking away
        termination_reason: Reason if terminated
        metadata: Additional session metadata
    """

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
        """Factory method to create a new session.

        Args:
            exam_id: External exam identifier
            user_id: User to proctor
            tenant_id: Tenant identifier
            config: Optional custom configuration
            metadata: Optional additional metadata

        Returns:
            New ProctorSession instance
        """
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
        """Start the proctoring session.

        Args:
            baseline_embedding: Initial face embedding for verification

        Raises:
            ValueError: If session cannot be started
        """
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
        """Terminate the session with reason.

        Args:
            reason: Why session was terminated
        """
        if self.is_terminal():
            return  # Already terminated

        self.status = SessionStatus.TERMINATED
        self.ended_at = datetime.utcnow()
        self.termination_reason = reason

    def flag(self) -> None:
        """Flag session as high risk."""
        if self.status == SessionStatus.ACTIVE:
            self.status = SessionStatus.FLAGGED

    def update_risk_score(self, score: float) -> None:
        """Update the aggregated risk score.

        Args:
            score: New risk score (0.0-1.0)
        """
        self.risk_score = max(0.0, min(1.0, score))

        # Auto-flag if critical threshold exceeded
        if self.risk_score >= self.config.risk_threshold_critical:
            self.flag()

    def record_verification(self, success: bool) -> None:
        """Record a verification attempt.

        Args:
            success: Whether verification succeeded
        """
        self.verification_count += 1
        if not success:
            self.verification_failures += 1

    def record_incident(self) -> None:
        """Increment incident count."""
        self.incident_count += 1

    def add_gaze_away_time(self, seconds: float) -> None:
        """Add time spent looking away.

        Args:
            seconds: Seconds spent looking away
        """
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
```

#### 3.2.2 ProctorIncident

```python
# app/domain/entities/proctor_incident.py

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


class IncidentSeverity(str, Enum):
    """Severity levels for incidents."""

    LOW = "low"           # Minor, informational
    MEDIUM = "medium"     # Concerning, needs review
    HIGH = "high"         # Serious violation
    CRITICAL = "critical" # Immediate action required


class ReviewAction(str, Enum):
    """Actions taken after reviewing incident."""

    DISMISSED = "dismissed"           # False positive
    ACKNOWLEDGED = "acknowledged"     # Noted, no action
    WARNING_ISSUED = "warning_issued" # Warning sent to user
    SESSION_PAUSED = "session_paused" # Session paused for review
    SESSION_TERMINATED = "session_terminated"  # Session ended
    ESCALATED = "escalated"           # Escalated to human proctor


@dataclass
class IncidentEvidence:
    """Evidence attached to an incident.

    Attributes:
        id: Evidence identifier
        incident_id: Parent incident
        evidence_type: Type of evidence
        storage_url: URL to stored evidence
        thumbnail_url: Optional thumbnail
        metadata: Additional metadata
        created_at: When captured
    """

    id: UUID
    incident_id: UUID
    evidence_type: str  # "image", "video_clip", "audio_clip", "screenshot"
    storage_url: str
    thumbnail_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProctorIncident:
    """Proctoring incident entity.

    Represents a detected suspicious event during a proctoring session.
    Immutable once created (except for review status).

    Attributes:
        id: Unique incident identifier
        session_id: Parent session
        incident_type: Type of incident
        severity: Severity level
        confidence: Detection confidence (0.0-1.0)
        timestamp: When incident occurred
        details: Incident-specific details
        evidence: List of evidence items
        reviewed: Whether incident has been reviewed
        reviewed_at: When reviewed
        reviewed_by: Who reviewed
        review_action: Action taken
        review_notes: Reviewer notes
    """

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
        severity: IncidentSeverity,
        confidence: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ProctorIncident":
        """Factory method to create incident.

        Args:
            session_id: Parent session ID
            incident_type: Type of incident
            severity: Severity level
            confidence: Detection confidence
            details: Optional details

        Returns:
            New ProctorIncident instance
        """
        return cls(
            id=uuid4(),
            session_id=session_id,
            incident_type=incident_type,
            severity=severity,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            details=details or {},
        )

    def add_evidence(self, evidence: IncidentEvidence) -> None:
        """Add evidence to incident.

        Args:
            evidence: Evidence to add
        """
        self.evidence.append(evidence)

    def mark_reviewed(
        self,
        reviewer: str,
        action: ReviewAction,
        notes: Optional[str] = None,
    ) -> None:
        """Mark incident as reviewed.

        Args:
            reviewer: Who reviewed
            action: Action taken
            notes: Optional notes
        """
        self.reviewed = True
        self.reviewed_at = datetime.utcnow()
        self.reviewed_by = reviewer
        self.review_action = action
        self.review_notes = notes

    def get_risk_contribution(self) -> float:
        """Calculate risk contribution based on severity and confidence.

        Returns:
            Risk contribution (0.0-1.0)
        """
        severity_weights = {
            IncidentSeverity.LOW: 0.1,
            IncidentSeverity.MEDIUM: 0.3,
            IncidentSeverity.HIGH: 0.6,
            IncidentSeverity.CRITICAL: 1.0,
        }

        base_weight = severity_weights.get(self.severity, 0.1)
        return base_weight * self.confidence

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
            "reviewed": self.reviewed,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "review_action": self.review_action.value if self.review_action else None,
            "review_notes": self.review_notes,
            "risk_contribution": self.get_risk_contribution(),
        }


# Severity mapping for incident types
INCIDENT_SEVERITY_MAP: Dict[IncidentType, IncidentSeverity] = {
    # Critical - immediate action
    IncidentType.MULTIPLE_FACES: IncidentSeverity.CRITICAL,
    IncidentType.FACE_NOT_MATCHED: IncidentSeverity.CRITICAL,
    IncidentType.PERSON_IN_BACKGROUND: IncidentSeverity.CRITICAL,

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

    # Low - informational
    IncidentType.FACE_NOT_DETECTED: IncidentSeverity.LOW,
    IncidentType.CAMERA_BLOCKED: IncidentSeverity.LOW,
    IncidentType.LOW_QUALITY_FEED: IncidentSeverity.LOW,
    IncidentType.EXCESSIVE_PAUSES: IncidentSeverity.LOW,
}


def get_default_severity(incident_type: IncidentType) -> IncidentSeverity:
    """Get default severity for incident type.

    Args:
        incident_type: Type of incident

    Returns:
        Default severity level
    """
    return INCIDENT_SEVERITY_MAP.get(incident_type, IncidentSeverity.MEDIUM)
```

#### 3.2.3 Analysis Results

```python
# app/domain/entities/proctor_analysis.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID


@dataclass(frozen=True)
class HeadPose:
    """Head orientation in 3D space.

    Attributes:
        pitch: Up/down rotation (degrees)
        yaw: Left/right rotation (degrees)
        roll: Tilt rotation (degrees)
    """

    pitch: float  # Nodding: negative = down, positive = up
    yaw: float    # Shaking: negative = left, positive = right
    roll: float   # Tilting: negative = left, positive = right

    def is_facing_forward(
        self,
        pitch_threshold: float = 20.0,
        yaw_threshold: float = 30.0,
    ) -> bool:
        """Check if head is facing approximately forward.

        Args:
            pitch_threshold: Max pitch deviation
            yaw_threshold: Max yaw deviation

        Returns:
            True if facing forward within thresholds
        """
        return abs(self.pitch) <= pitch_threshold and abs(self.yaw) <= yaw_threshold

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "pitch": self.pitch,
            "yaw": self.yaw,
            "roll": self.roll,
        }


@dataclass(frozen=True)
class GazeDirection:
    """Eye gaze direction estimation.

    Attributes:
        x: Horizontal gaze (-1.0 to 1.0, negative = left)
        y: Vertical gaze (-1.0 to 1.0, negative = down)
        on_screen: Whether gaze is estimated to be on screen
        confidence: Estimation confidence
    """

    x: float
    y: float
    on_screen: bool
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "on_screen": self.on_screen,
            "confidence": self.confidence,
        }


@dataclass
class GazeAnalysisResult:
    """Result of gaze/attention analysis.

    Attributes:
        session_id: Session being analyzed
        timestamp: Analysis timestamp
        head_pose: Detected head pose
        gaze_direction: Estimated gaze direction
        face_visible: Whether face is visible
        looking_at_screen: Combined assessment
        attention_score: Attention level (0.0-1.0)
        off_screen_duration_sec: Current off-screen duration
    """

    session_id: UUID
    timestamp: datetime
    head_pose: Optional[HeadPose]
    gaze_direction: Optional[GazeDirection]
    face_visible: bool
    looking_at_screen: bool
    attention_score: float
    off_screen_duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "head_pose": self.head_pose.to_dict() if self.head_pose else None,
            "gaze_direction": self.gaze_direction.to_dict() if self.gaze_direction else None,
            "face_visible": self.face_visible,
            "looking_at_screen": self.looking_at_screen,
            "attention_score": self.attention_score,
            "off_screen_duration_sec": self.off_screen_duration_sec,
        }


@dataclass(frozen=True)
class DetectedObject:
    """Detected object in frame.

    Attributes:
        object_class: Classification (phone, book, person, etc.)
        confidence: Detection confidence
        bounding_box: (x, y, width, height) normalized 0-1
        is_prohibited: Whether object is prohibited
    """

    object_class: str
    confidence: float
    bounding_box: Tuple[float, float, float, float]
    is_prohibited: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "object_class": self.object_class,
            "confidence": self.confidence,
            "bounding_box": {
                "x": self.bounding_box[0],
                "y": self.bounding_box[1],
                "width": self.bounding_box[2],
                "height": self.bounding_box[3],
            },
            "is_prohibited": self.is_prohibited,
        }


@dataclass
class ObjectDetectionResult:
    """Result of object detection analysis.

    Attributes:
        session_id: Session being analyzed
        timestamp: Analysis timestamp
        objects: List of detected objects
        prohibited_objects: Filtered list of prohibited objects
        frame_clear: Whether frame is clear of prohibited objects
    """

    session_id: UUID
    timestamp: datetime
    objects: List[DetectedObject] = field(default_factory=list)

    @property
    def prohibited_objects(self) -> List[DetectedObject]:
        """Get only prohibited objects."""
        return [obj for obj in self.objects if obj.is_prohibited]

    @property
    def frame_clear(self) -> bool:
        """Check if frame is clear of prohibited objects."""
        return len(self.prohibited_objects) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "objects": [obj.to_dict() for obj in self.objects],
            "prohibited_count": len(self.prohibited_objects),
            "frame_clear": self.frame_clear,
        }


@dataclass
class AudioAnalysisResult:
    """Result of audio analysis.

    Attributes:
        session_id: Session being analyzed
        timestamp: Analysis timestamp
        voice_detected: Whether voice activity detected
        speaker_count: Estimated number of speakers
        background_noise_level: Background noise level (dB)
        suspicious_keywords: Detected suspicious keywords
        is_suspicious: Overall suspicion flag
    """

    session_id: UUID
    timestamp: datetime
    voice_detected: bool
    speaker_count: int
    background_noise_level: float
    suspicious_keywords: List[str] = field(default_factory=list)
    is_suspicious: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "voice_detected": self.voice_detected,
            "speaker_count": self.speaker_count,
            "background_noise_level": self.background_noise_level,
            "suspicious_keywords": self.suspicious_keywords,
            "is_suspicious": self.is_suspicious,
        }


@dataclass
class FrameAnalysisResult:
    """Combined result of all frame analysis.

    Aggregates results from face verification, gaze tracking,
    object detection, and audio analysis into a single result.
    """

    session_id: UUID
    timestamp: datetime
    frame_number: int

    # Face verification
    face_detected: bool = True
    face_matched: bool = True
    face_confidence: float = 1.0
    face_count: int = 1
    liveness_score: float = 1.0
    quality_score: float = 1.0

    # Gaze analysis
    gaze_result: Optional[GazeAnalysisResult] = None

    # Object detection
    object_result: Optional[ObjectDetectionResult] = None

    # Audio analysis
    audio_result: Optional[AudioAnalysisResult] = None

    # Aggregated risk
    frame_risk_score: float = 0.0
    incidents_generated: List[str] = field(default_factory=list)

    def calculate_risk_score(self) -> float:
        """Calculate aggregated risk score for this frame.

        Returns:
            Risk score (0.0-1.0)
        """
        risks = []

        # Identity risk
        if not self.face_detected:
            risks.append(0.3)
        if not self.face_matched:
            risks.append(0.9)
        if self.face_count > 1:
            risks.append(0.8)
        if self.liveness_score < 0.5:
            risks.append(0.7)

        # Attention risk
        if self.gaze_result and not self.gaze_result.looking_at_screen:
            risks.append(0.2 + (self.gaze_result.off_screen_duration_sec * 0.05))

        # Object risk
        if self.object_result and not self.object_result.frame_clear:
            for obj in self.object_result.prohibited_objects:
                if obj.object_class == "phone":
                    risks.append(0.7)
                elif obj.object_class == "person":
                    risks.append(0.8)
                else:
                    risks.append(0.5)

        # Audio risk
        if self.audio_result and self.audio_result.is_suspicious:
            if self.audio_result.speaker_count > 1:
                risks.append(0.6)
            else:
                risks.append(0.3)

        # Aggregate (max with decay for multiple risks)
        if not risks:
            return 0.0

        risks.sort(reverse=True)
        total = risks[0]
        for i, risk in enumerate(risks[1:], 1):
            total += risk * (0.5 ** i)  # Diminishing returns

        return min(1.0, total)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "frame_number": self.frame_number,
            "face_detected": self.face_detected,
            "face_matched": self.face_matched,
            "face_confidence": self.face_confidence,
            "face_count": self.face_count,
            "liveness_score": self.liveness_score,
            "quality_score": self.quality_score,
            "gaze": self.gaze_result.to_dict() if self.gaze_result else None,
            "objects": self.object_result.to_dict() if self.object_result else None,
            "audio": self.audio_result.to_dict() if self.audio_result else None,
            "frame_risk_score": self.frame_risk_score,
            "incidents_generated": self.incidents_generated,
        }
```

---

## 4. Use Cases

### 4.1 Use Case Diagram

```
                    ┌─────────────────────────────────────────┐
                    │           PROCTORING SERVICE            │
                    │                                         │
    ┌───────┐       │  ┌─────────────────────────────────┐   │
    │       │       │  │     Session Management          │   │
    │       │───────┼─▶│  - CreateSession                │   │
    │       │       │  │  - StartSession                 │   │
    │ Exam  │       │  │  - PauseSession                 │   │
    │Platform│      │  │  - ResumeSession                │   │
    │       │       │  │  - EndSession                   │   │
    │       │       │  │  - GetSessionStatus             │   │
    │       │       │  └─────────────────────────────────┘   │
    │       │       │                                         │
    │       │       │  ┌─────────────────────────────────┐   │
    │       │───────┼─▶│     Verification                │   │
    │       │       │  │  - SubmitFrame                  │   │
    │       │       │  │  - VerifyIdentity               │   │
    │       │       │  │  - CheckLiveness                │   │
    └───────┘       │  └─────────────────────────────────┘   │
                    │                                         │
    ┌───────┐       │  ┌─────────────────────────────────┐   │
    │       │       │  │     Analysis                    │   │
    │       │───────┼─▶│  - AnalyzeGaze                  │   │
    │ Test  │       │  │  - DetectObjects                │   │
    │ Taker │       │  │  - AnalyzeAudio                 │   │
    │       │       │  │  - AnalyzeFrame                 │   │
    │       │       │  └─────────────────────────────────┘   │
    └───────┘       │                                         │
                    │  ┌─────────────────────────────────┐   │
    ┌───────┐       │  │     Incident Management         │   │       ┌─────────┐
    │       │       │  │  - CreateIncident               │───┼──────▶│ Webhook │
    │Proctor│───────┼─▶│  - ListIncidents                │   │       │ System  │
    │/Admin │       │  │  - ReviewIncident               │   │       └─────────┘
    │       │       │  │  - GetSessionReport             │   │
    │       │       │  └─────────────────────────────────┘   │
    └───────┘       │                                         │
                    └─────────────────────────────────────────┘
```

### 4.2 Use Case Specifications

#### UC-01: Create Proctoring Session

```yaml
Name: CreateProctorSession
Actor: Exam Platform
Preconditions:
  - Valid API key with proctoring scope
  - User exists and is enrolled (has face embedding)

Input:
  exam_id: string (required)
  user_id: string (required)
  config: SessionConfig (optional)
  metadata: object (optional)

Output:
  session: ProctorSession

Flow:
  1. Validate API key and permissions
  2. Verify user has enrolled face embedding
  3. Create session with CREATED status
  4. Store session in repository
  5. Return session details

Exceptions:
  - UserNotEnrolled: User has no face embedding
  - InvalidConfiguration: Config values out of range
  - QuotaExceeded: Tenant has reached session limit
```

#### UC-02: Start Proctoring Session

```yaml
Name: StartProctorSession
Actor: Exam Platform
Preconditions:
  - Session exists in CREATED status
  - Initial frame provided for verification

Input:
  session_id: UUID (required)
  initial_frame: Image (required)

Output:
  session: ProctorSession (updated)
  verification: VerificationResult

Flow:
  1. Load session by ID
  2. Validate session can be started
  3. Perform initial face verification against enrolled embedding
  4. Perform liveness check
  5. If verification passes:
     a. Store baseline embedding from frame
     b. Update session status to ACTIVE
     c. Set started_at timestamp
  6. If verification fails:
     a. Return failure with details
     b. Session remains in CREATED status
  7. Trigger session.started webhook
  8. Return updated session and verification result

Exceptions:
  - SessionNotFound: Session ID not found
  - InvalidSessionState: Session not in CREATED status
  - VerificationFailed: Face doesn't match enrolled user
  - LivenessCheckFailed: Liveness detection failed
```

#### UC-03: Submit Frame for Analysis

```yaml
Name: SubmitFrame
Actor: Test Taker (via SDK)
Preconditions:
  - Session is ACTIVE
  - Frame meets quality requirements

Input:
  session_id: UUID (required)
  frame: Image (required)
  audio_chunk: bytes (optional)
  client_timestamp: datetime (optional)

Output:
  analysis: FrameAnalysisResult
  incidents: List[ProctorIncident]
  session_status: SessionStatus

Flow:
  1. Validate session is active
  2. Check frame quality (blur, lighting, size)
  3. Run analysis pipeline in parallel:
     a. Face detection and verification
     b. Multi-face detection
     c. Gaze/head pose analysis
     d. Object detection
     e. Audio analysis (if provided)
  4. Aggregate results into FrameAnalysisResult
  5. Generate incidents for violations
  6. Update session risk score
  7. Check if session should be flagged/terminated
  8. Store analysis event (sampling)
  9. Return results

Exceptions:
  - SessionNotActive: Session not in active state
  - LowQualityFrame: Frame doesn't meet requirements
  - AnalysisTimeout: Analysis took too long
```

#### UC-04: Periodic Verification

```yaml
Name: PeriodicVerification
Actor: System (scheduled)
Preconditions:
  - Session is ACTIVE
  - Verification interval elapsed

Input:
  session_id: UUID
  frame: Image

Output:
  verified: bool
  confidence: float
  incidents: List[ProctorIncident]

Flow:
  1. Load session and baseline embedding
  2. Detect face in frame
  3. Extract embedding from detected face
  4. Compare against baseline embedding
  5. Perform liveness check
  6. If verification fails:
     a. Increment failure count
     b. Create incident
     c. If max failures exceeded, flag session
  7. Update session verification stats
  8. Return result

Exceptions:
  - NoFaceDetected: No face in frame
  - VerificationFailed: Face doesn't match baseline
```

#### UC-05: Review Incident

```yaml
Name: ReviewIncident
Actor: Proctor/Admin
Preconditions:
  - Incident exists and is not reviewed
  - User has review permissions

Input:
  incident_id: UUID (required)
  action: ReviewAction (required)
  notes: string (optional)

Output:
  incident: ProctorIncident (updated)
  session: ProctorSession (if affected)

Flow:
  1. Load incident by ID
  2. Validate incident not already reviewed
  3. Apply review action:
     - DISMISSED: Mark as false positive
     - ACKNOWLEDGED: Note and continue
     - WARNING_ISSUED: Send warning to user
     - SESSION_PAUSED: Pause the session
     - SESSION_TERMINATED: End the session
     - ESCALATED: Notify human proctor
  4. Update incident with review details
  5. If session affected, update session status
  6. Trigger incident.reviewed webhook
  7. Return updated incident

Exceptions:
  - IncidentNotFound: Incident ID not found
  - AlreadyReviewed: Incident already reviewed
  - InvalidAction: Action not appropriate for incident
```

---

## 5. API Specification

### 5.1 REST Endpoints

#### Session Management

```yaml
# Create Session
POST /api/v1/proctor/sessions
Request:
  Content-Type: application/json
  X-API-Key: {api_key}
  Body:
    exam_id: string (required)
    user_id: string (required)
    config:
      verification_interval_sec: integer (default: 60)
      verification_threshold: number (default: 0.6)
      gaze_away_threshold_sec: number (default: 5.0)
      enable_object_detection: boolean (default: true)
      enable_audio_monitoring: boolean (default: true)
    metadata: object (optional)
Response:
  201 Created:
    id: string (UUID)
    exam_id: string
    user_id: string
    status: "created"
    config: object
    created_at: string (ISO 8601)
  400 Bad Request:
    error: "validation_error"
    details: [...]
  404 Not Found:
    error: "user_not_enrolled"
    message: "User has no enrolled face embedding"

# Get Session
GET /api/v1/proctor/sessions/{session_id}
Response:
  200 OK:
    id: string
    exam_id: string
    user_id: string
    status: string
    risk_score: number
    verification_count: integer
    verification_failures: integer
    incident_count: integer
    started_at: string | null
    ended_at: string | null
    duration_seconds: number
    config: object

# Start Session
POST /api/v1/proctor/sessions/{session_id}/start
Request:
  Content-Type: multipart/form-data
  Body:
    frame: file (image/jpeg, image/png)
Response:
  200 OK:
    session:
      id: string
      status: "active"
      started_at: string
    verification:
      verified: boolean
      confidence: number
      liveness_score: number
  400 Bad Request:
    error: "verification_failed"
    details:
      face_detected: boolean
      face_matched: boolean
      liveness_passed: boolean

# Pause Session
POST /api/v1/proctor/sessions/{session_id}/pause
Response:
  200 OK:
    session:
      status: "paused"
      paused_at: string

# Resume Session
POST /api/v1/proctor/sessions/{session_id}/resume
Request:
  Content-Type: multipart/form-data
  Body:
    frame: file (required for re-verification)
Response:
  200 OK:
    session:
      status: "active"
    verification:
      verified: boolean
      confidence: number

# End Session
POST /api/v1/proctor/sessions/{session_id}/end
Request:
  Body:
    reason: string (optional)
Response:
  200 OK:
    session:
      status: "completed"
      ended_at: string
      duration_seconds: number
      verification_success_rate: number
      incident_count: integer
      risk_score: number
```

#### Frame Submission

```yaml
# Submit Frame
POST /api/v1/proctor/sessions/{session_id}/frames
Request:
  Content-Type: multipart/form-data
  Body:
    frame: file (required)
    audio: file (optional, audio/wav)
    timestamp: string (optional, ISO 8601)
Response:
  200 OK:
    analysis:
      face_detected: boolean
      face_matched: boolean
      face_confidence: number
      face_count: integer
      liveness_score: number
      looking_at_screen: boolean
      attention_score: number
      objects_detected: [
        { class: string, confidence: number, prohibited: boolean }
      ]
      frame_risk_score: number
    incidents: [
      {
        id: string
        type: string
        severity: string
        confidence: number
      }
    ]
    session:
      status: string
      risk_score: number
  400 Bad Request:
    error: "low_quality_frame"
    details:
      blur_score: number
      brightness: number
      face_size: number

# Get Session Status (lightweight)
GET /api/v1/proctor/sessions/{session_id}/status
Response:
  200 OK:
    status: string
    risk_score: number
    is_flagged: boolean
    last_verification_at: string
    incident_count: integer
```

#### Incident Management

```yaml
# List Session Incidents
GET /api/v1/proctor/sessions/{session_id}/incidents
Query Parameters:
  severity: string (filter by severity)
  type: string (filter by type)
  reviewed: boolean (filter by review status)
  limit: integer (default: 50)
  offset: integer (default: 0)
Response:
  200 OK:
    incidents: [...]
    total: integer
    has_more: boolean

# Get Incident Details
GET /api/v1/proctor/incidents/{incident_id}
Response:
  200 OK:
    id: string
    session_id: string
    type: string
    severity: string
    confidence: number
    timestamp: string
    details: object
    evidence: [
      {
        id: string
        type: string
        url: string
        thumbnail_url: string
      }
    ]
    reviewed: boolean
    review_action: string | null
    review_notes: string | null

# Review Incident
PATCH /api/v1/proctor/incidents/{incident_id}
Request:
  Body:
    action: string (required: dismissed, acknowledged, warning_issued, session_paused, session_terminated, escalated)
    notes: string (optional)
Response:
  200 OK:
    incident:
      reviewed: true
      reviewed_at: string
      review_action: string
    session:
      status: string (if changed)

# Get Incident Evidence
GET /api/v1/proctor/incidents/{incident_id}/evidence/{evidence_id}
Response:
  302 Redirect to signed URL
```

#### Reports

```yaml
# Get Session Report
GET /api/v1/proctor/sessions/{session_id}/report
Response:
  200 OK:
    session:
      id: string
      exam_id: string
      user_id: string
      status: string
      duration_seconds: number
      risk_score: number
    verification:
      total_count: integer
      success_count: integer
      failure_count: integer
      success_rate: number
    attention:
      total_gaze_away_seconds: number
      average_attention_score: number
    incidents:
      total: integer
      by_severity:
        critical: integer
        high: integer
        medium: integer
        low: integer
      by_type: object
    timeline: [
      {
        timestamp: string
        event_type: string
        details: object
      }
    ]

# Get Session Timeline
GET /api/v1/proctor/sessions/{session_id}/timeline
Query Parameters:
  start: string (ISO 8601)
  end: string (ISO 8601)
  include_frames: boolean (default: false)
Response:
  200 OK:
    events: [
      {
        timestamp: string
        type: string
        data: object
      }
    ]
```

### 5.2 WebSocket API (Real-time)

```yaml
# Connect to Session Stream
WS /api/v1/proctor/sessions/{session_id}/stream

# Client → Server Messages
frame:
  type: "frame"
  data: base64 (image)
  timestamp: string

audio:
  type: "audio"
  data: base64 (audio chunk)
  timestamp: string

# Server → Client Messages
analysis:
  type: "analysis"
  data:
    face_detected: boolean
    face_matched: boolean
    looking_at_screen: boolean
    risk_score: number

incident:
  type: "incident"
  data:
    id: string
    type: string
    severity: string

status:
  type: "status"
  data:
    status: string
    message: string

error:
  type: "error"
  code: string
  message: string
```

### 5.3 Webhook Events

```yaml
Events:
  - proctor.session.created
  - proctor.session.started
  - proctor.session.paused
  - proctor.session.resumed
  - proctor.session.completed
  - proctor.session.terminated
  - proctor.session.flagged
  - proctor.incident.created
  - proctor.incident.reviewed
  - proctor.verification.failed

Payload Format:
  event_id: string (UUID)
  event_type: string
  timestamp: string (ISO 8601)
  tenant_id: string
  data:
    session_id: string
    ... (event-specific data)

Headers:
  X-Event-ID: {event_id}
  X-Event-Type: {event_type}
  X-Webhook-Signature: sha256={hmac}
  Content-Type: application/json
```

---

## 6. Infrastructure Components

### 6.1 Repository Interfaces

```python
# app/domain/interfaces/proctor_session_repository.py

from datetime import datetime
from typing import List, Optional, Protocol
from uuid import UUID

from app.domain.entities.proctor_session import ProctorSession, SessionStatus


class IProctorSessionRepository(Protocol):
    """Repository interface for proctoring sessions."""

    async def save(self, session: ProctorSession) -> None:
        """Save or update a session."""
        ...

    async def find_by_id(
        self,
        session_id: UUID,
        tenant_id: Optional[str] = None,
    ) -> Optional[ProctorSession]:
        """Find session by ID."""
        ...

    async def find_by_exam_id(
        self,
        exam_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[ProctorSession]:
        """Find sessions by exam ID."""
        ...

    async def find_by_user_id(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
    ) -> List[ProctorSession]:
        """Find sessions by user ID."""
        ...

    async def find_active(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[ProctorSession]:
        """Find all active sessions."""
        ...

    async def delete(
        self,
        session_id: UUID,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Delete a session."""
        ...

    async def count(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
    ) -> int:
        """Count sessions."""
        ...


# app/domain/interfaces/proctor_incident_repository.py

class IProctorIncidentRepository(Protocol):
    """Repository interface for proctoring incidents."""

    async def save(self, incident: ProctorIncident) -> None:
        """Save an incident."""
        ...

    async def find_by_id(self, incident_id: UUID) -> Optional[ProctorIncident]:
        """Find incident by ID."""
        ...

    async def find_by_session_id(
        self,
        session_id: UUID,
        severity: Optional[IncidentSeverity] = None,
        incident_type: Optional[IncidentType] = None,
        reviewed: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorIncident]:
        """Find incidents by session ID."""
        ...

    async def count_by_session_id(
        self,
        session_id: UUID,
        severity: Optional[IncidentSeverity] = None,
    ) -> int:
        """Count incidents for session."""
        ...

    async def update(self, incident: ProctorIncident) -> None:
        """Update an incident."""
        ...
```

### 6.2 Analysis Interfaces

```python
# app/domain/interfaces/gaze_tracker.py

from typing import Optional, Protocol

import numpy as np

from app.domain.entities.proctor_analysis import GazeAnalysisResult, HeadPose


class IGazeTracker(Protocol):
    """Interface for gaze and attention tracking."""

    def analyze(
        self,
        image: np.ndarray,
        session_id: UUID,
    ) -> GazeAnalysisResult:
        """Analyze gaze and head pose from image.

        Args:
            image: BGR image array
            session_id: Session being analyzed

        Returns:
            GazeAnalysisResult with head pose and gaze direction
        """
        ...

    def get_head_pose(self, image: np.ndarray) -> Optional[HeadPose]:
        """Get head pose from image.

        Args:
            image: BGR image array

        Returns:
            HeadPose or None if face not detected
        """
        ...


# app/domain/interfaces/object_detector.py

class IObjectDetector(Protocol):
    """Interface for object detection."""

    def detect(
        self,
        image: np.ndarray,
        session_id: UUID,
        prohibited_classes: Optional[List[str]] = None,
    ) -> ObjectDetectionResult:
        """Detect objects in image.

        Args:
            image: BGR image array
            session_id: Session being analyzed
            prohibited_classes: List of prohibited object classes

        Returns:
            ObjectDetectionResult with detected objects
        """
        ...


# app/domain/interfaces/audio_analyzer.py

class IAudioAnalyzer(Protocol):
    """Interface for audio analysis."""

    def analyze(
        self,
        audio_data: bytes,
        sample_rate: int,
        session_id: UUID,
    ) -> AudioAnalysisResult:
        """Analyze audio chunk.

        Args:
            audio_data: Raw audio bytes
            sample_rate: Audio sample rate
            session_id: Session being analyzed

        Returns:
            AudioAnalysisResult with voice activity and speaker count
        """
        ...
```

### 6.3 Database Schema

```sql
-- migrations/003_proctoring_tables.sql

-- Proctor Sessions
CREATE TABLE proctor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    risk_score FLOAT NOT NULL DEFAULT 0.0,
    config JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    baseline_embedding vector(512),
    verification_count INTEGER NOT NULL DEFAULT 0,
    verification_failures INTEGER NOT NULL DEFAULT 0,
    incident_count INTEGER NOT NULL DEFAULT 0,
    total_gaze_away_sec FLOAT NOT NULL DEFAULT 0.0,
    termination_reason VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    paused_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_user_embedding
        FOREIGN KEY (user_id, tenant_id)
        REFERENCES face_embeddings(user_id, tenant_id)
);

-- Indexes
CREATE INDEX idx_proctor_sessions_exam ON proctor_sessions(exam_id, tenant_id);
CREATE INDEX idx_proctor_sessions_user ON proctor_sessions(user_id, tenant_id);
CREATE INDEX idx_proctor_sessions_status ON proctor_sessions(status, tenant_id);
CREATE INDEX idx_proctor_sessions_active ON proctor_sessions(tenant_id)
    WHERE status IN ('active', 'flagged');

-- Proctor Incidents
CREATE TABLE proctor_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(255),
    review_action VARCHAR(50),
    review_notes TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_proctor_incidents_session ON proctor_incidents(session_id);
CREATE INDEX idx_proctor_incidents_severity ON proctor_incidents(session_id, severity);
CREATE INDEX idx_proctor_incidents_unreviewed ON proctor_incidents(session_id)
    WHERE reviewed = FALSE;

-- Incident Evidence
CREATE TABLE incident_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES proctor_incidents(id) ON DELETE CASCADE,
    evidence_type VARCHAR(50) NOT NULL,
    storage_url TEXT NOT NULL,
    thumbnail_url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_incident_evidence_incident ON incident_evidence(incident_id);

-- Verification Events (sampled, for analytics)
CREATE TABLE verification_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    face_detected BOOLEAN NOT NULL,
    face_matched BOOLEAN NOT NULL,
    confidence FLOAT NOT NULL,
    liveness_score FLOAT,
    quality_score FLOAT,
    face_count INTEGER NOT NULL DEFAULT 1,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_events_session ON verification_events(session_id, timestamp);

-- Partitioning for verification_events (by month)
-- CREATE TABLE verification_events_y2024m12 PARTITION OF verification_events
--     FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

-- Session Config Templates
CREATE TABLE session_config_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE(tenant_id, name)
);
```

---

## 7. Data Flow

### 7.1 Frame Analysis Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRAME SUBMISSION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

Client                API                  Service                    Storage
  │                    │                      │                          │
  │ POST /frames       │                      │                          │
  │ {frame, audio}     │                      │                          │
  │───────────────────▶│                      │                          │
  │                    │                      │                          │
  │                    │ Validate Session     │                          │
  │                    │─────────────────────▶│                          │
  │                    │                      │                          │
  │                    │                      │ Load Session             │
  │                    │                      │─────────────────────────▶│
  │                    │                      │◀─────────────────────────│
  │                    │                      │                          │
  │                    │                      │ ┌─────────────────────┐  │
  │                    │                      │ │ PARALLEL ANALYSIS   │  │
  │                    │                      │ │                     │  │
  │                    │                      │ │ ┌─────────────────┐ │  │
  │                    │                      │ │ │ Face Verify     │ │  │
  │                    │                      │ │ └─────────────────┘ │  │
  │                    │                      │ │ ┌─────────────────┐ │  │
  │                    │                      │ │ │ Gaze Track      │ │  │
  │                    │                      │ │ └─────────────────┘ │  │
  │                    │                      │ │ ┌─────────────────┐ │  │
  │                    │                      │ │ │ Object Detect   │ │  │
  │                    │                      │ │ └─────────────────┘ │  │
  │                    │                      │ │ ┌─────────────────┐ │  │
  │                    │                      │ │ │ Audio Analyze   │ │  │
  │                    │                      │ │ └─────────────────┘ │  │
  │                    │                      │ └─────────────────────┘  │
  │                    │                      │                          │
  │                    │                      │ Fuse Results             │
  │                    │                      │ Calculate Risk           │
  │                    │                      │                          │
  │                    │                      │ Generate Incidents       │
  │                    │                      │─────────────────────────▶│
  │                    │                      │                          │
  │                    │                      │ Update Session           │
  │                    │                      │─────────────────────────▶│
  │                    │                      │                          │
  │                    │ FrameAnalysisResult  │                          │
  │                    │◀─────────────────────│                          │
  │                    │                      │                          │
  │ 200 OK             │                      │                          │
  │ {analysis,         │                      │                          │
  │  incidents,        │                      │                          │
  │  session_status}   │                      │                          │
  │◀───────────────────│                      │                          │
  │                    │                      │                          │
  │                    │                      │ [If Critical Incident]   │
  │                    │                      │ Send Webhook             │
  │                    │                      │─────────────────────────▶│ Webhook
  │                    │                      │                          │
```

### 7.2 Risk Score Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│                    RISK SCORE AGGREGATION                        │
└─────────────────────────────────────────────────────────────────┘

Input Signals:
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ Identity Risk   │   │ Attention Risk  │   │ Environment Risk│
│                 │   │                 │   │                 │
│ • Face match    │   │ • Gaze away     │   │ • Objects       │
│ • Liveness      │   │ • Head pose     │   │ • Persons       │
│ • Face count    │   │ • Duration      │   │ • Audio         │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FUSION ENGINE                               │
│                                                                  │
│  risk_identity = w1 * (1 - face_confidence) +                   │
│                  w2 * (1 - liveness_score) +                     │
│                  w3 * (face_count > 1 ? 0.8 : 0)                │
│                                                                  │
│  risk_attention = w4 * gaze_away_ratio +                        │
│                   w5 * head_deviation_score                      │
│                                                                  │
│  risk_environment = w6 * max(object_risks) +                    │
│                     w7 * audio_risk                              │
│                                                                  │
│  total_risk = α * risk_identity +                               │
│               β * risk_attention +                               │
│               γ * risk_environment                               │
│                                                                  │
│  Weights: α=0.5, β=0.25, γ=0.25 (configurable)                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION RISK UPDATE                           │
│                                                                  │
│  session.risk_score = EMA(session.risk_score, frame_risk)       │
│                                                                  │
│  if session.risk_score > CRITICAL_THRESHOLD:                    │
│      session.flag()                                              │
│      webhook.send('session.flagged')                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Configuration

### 8.1 Environment Variables

```bash
# Proctoring Feature Flags
PROCTORING_ENABLED=true
PROCTORING_MAX_CONCURRENT_SESSIONS=10000

# Verification Settings
PROCTOR_VERIFICATION_INTERVAL_SEC=60
PROCTOR_VERIFICATION_THRESHOLD=0.6
PROCTOR_MAX_VERIFICATION_FAILURES=3

# Gaze Tracking
PROCTOR_GAZE_AWAY_THRESHOLD_SEC=5.0
PROCTOR_GAZE_SENSITIVITY=0.7
PROCTOR_HEAD_POSE_PITCH_THRESHOLD=20.0
PROCTOR_HEAD_POSE_YAW_THRESHOLD=30.0

# Object Detection
PROCTOR_OBJECT_DETECTION_ENABLED=true
PROCTOR_OBJECT_DETECTION_MODEL=yolov8n
PROCTOR_OBJECT_CONFIDENCE_THRESHOLD=0.5
PROCTOR_PROHIBITED_OBJECTS=phone,book,laptop,tablet,person

# Audio Analysis
PROCTOR_AUDIO_MONITORING_ENABLED=true
PROCTOR_AUDIO_VAD_THRESHOLD=0.5
PROCTOR_AUDIO_MULTI_SPEAKER_THRESHOLD=0.7

# Risk Thresholds
PROCTOR_RISK_THRESHOLD_WARNING=0.5
PROCTOR_RISK_THRESHOLD_CRITICAL=0.8
PROCTOR_AUTO_TERMINATE_ON_CRITICAL=false

# Session Limits
PROCTOR_MAX_PAUSE_DURATION_SEC=300
PROCTOR_SESSION_TIMEOUT_SEC=14400
PROCTOR_MAX_SESSIONS_PER_USER=1

# Evidence Storage
PROCTOR_EVIDENCE_STORAGE=s3
PROCTOR_EVIDENCE_BUCKET=proctoring-evidence
PROCTOR_EVIDENCE_RETENTION_DAYS=90

# Webhooks
PROCTOR_WEBHOOK_EVENTS=session.flagged,incident.created,session.terminated
```

### 8.2 Default Session Config

```python
DEFAULT_SESSION_CONFIG = SessionConfig(
    verification_interval_sec=60,
    verification_threshold=0.6,
    max_verification_failures=3,
    gaze_away_threshold_sec=5.0,
    gaze_sensitivity=0.7,
    enable_object_detection=True,
    enable_audio_monitoring=True,
    enable_multi_face_detection=True,
    risk_threshold_warning=0.5,
    risk_threshold_critical=0.8,
    max_pause_duration_sec=300,
    session_timeout_sec=14400,
)
```

---

## 9. Security & Privacy

### 9.1 Data Classification

| Data Type | Classification | Retention | Encryption |
|-----------|---------------|-----------|------------|
| Face Images | Biometric (Special) | Session only | AES-256 |
| Face Embeddings | Biometric (Special) | Until deletion | AES-256 |
| Session Records | PII | 1 year | AES-256 |
| Incident Evidence | Biometric (Special) | 90 days | AES-256 |
| Analytics | Anonymized | 2 years | Standard |

### 9.2 Privacy Controls

```yaml
Data Minimization:
  - Process frames in memory, don't store
  - Store only embeddings, not raw images
  - Sample verification events (1 in 10)
  - Delete evidence after retention period

Consent Management:
  - Explicit consent required before session
  - Clear disclosure of data collection
  - Right to withdraw consent
  - Data export on request

Access Controls:
  - Role-based access to incidents
  - Audit log for all data access
  - Admin approval for exports
  - Tenant isolation enforced
```

### 9.3 GDPR Compliance Checklist

- [ ] Data Protection Impact Assessment (DPIA) completed
- [ ] Privacy notice updated for proctoring
- [ ] Consent mechanism implemented
- [ ] Data Subject Access Request (DSAR) process
- [ ] Right to erasure implemented
- [ ] Data retention policy enforced
- [ ] Cross-border transfer safeguards
- [ ] Data Processing Agreement (DPA) template

---

## 10. Monitoring & Observability

### 10.1 New Metrics

```python
# Proctoring-specific Prometheus metrics

# Session metrics
PROCTOR_SESSIONS_TOTAL = Counter(
    "biometric_proctor_sessions_total",
    "Total proctoring sessions",
    ["tenant_id", "status"],
)

PROCTOR_SESSIONS_ACTIVE = Gauge(
    "biometric_proctor_sessions_active",
    "Currently active proctoring sessions",
    ["tenant_id"],
)

PROCTOR_SESSION_DURATION = Histogram(
    "biometric_proctor_session_duration_seconds",
    "Session duration in seconds",
    ["status"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400),
)

# Verification metrics
PROCTOR_VERIFICATIONS_TOTAL = Counter(
    "biometric_proctor_verifications_total",
    "Total verification attempts",
    ["result"],  # success, failure
)

PROCTOR_VERIFICATION_LATENCY = Histogram(
    "biometric_proctor_verification_latency_seconds",
    "Verification latency",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

# Incident metrics
PROCTOR_INCIDENTS_TOTAL = Counter(
    "biometric_proctor_incidents_total",
    "Total incidents created",
    ["type", "severity"],
)

# Analysis metrics
PROCTOR_FRAME_ANALYSIS_LATENCY = Histogram(
    "biometric_proctor_frame_analysis_latency_seconds",
    "Frame analysis latency",
    ["component"],  # face, gaze, object, audio, total
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0),
)

# Risk metrics
PROCTOR_RISK_SCORE = Histogram(
    "biometric_proctor_risk_score",
    "Session risk scores",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
```

### 10.2 Alerts

```yaml
# Add to monitoring/prometheus/alerts.yml

- alert: ProctorHighIncidentRate
  expr: |
    sum(rate(biometric_proctor_incidents_total{severity="critical"}[5m])) > 1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High critical incident rate in proctoring"

- alert: ProctorVerificationFailureRate
  expr: |
    sum(rate(biometric_proctor_verifications_total{result="failure"}[5m]))
    /
    sum(rate(biometric_proctor_verifications_total[5m])) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "High verification failure rate"

- alert: ProctorAnalysisLatency
  expr: |
    histogram_quantile(0.95, rate(biometric_proctor_frame_analysis_latency_seconds_bucket{component="total"}[5m])) > 1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High frame analysis latency"
```

---

## 11. Implementation Phases

### Phase 1: Core Session Management (Weeks 1-2)

```
Tasks:
├── Domain Entities
│   ├── ProctorSession entity
│   ├── SessionConfig value object
│   └── SessionStatus enum
├── Repository
│   ├── IProctorSessionRepository interface
│   └── PostgresSessionRepository implementation
├── Use Cases
│   ├── CreateProctorSession
│   ├── StartProctorSession
│   ├── PauseProctorSession
│   ├── ResumeProctorSession
│   └── EndProctorSession
├── API Routes
│   └── /api/v1/proctor/sessions/*
├── Database
│   └── Migration for proctor_sessions table
└── Tests
    ├── Unit tests for entities
    ├── Unit tests for use cases
    └── Integration tests for API
```

### Phase 2: Continuous Verification (Weeks 3-4)

```
Tasks:
├── Analysis Pipeline
│   ├── FrameAnalysisResult entity
│   └── VerificationEvent entity
├── Use Cases
│   ├── SubmitFrame
│   ├── VerifyIdentity (continuous)
│   └── CheckSessionStatus
├── Risk Scoring
│   ├── RiskCalculator service
│   └── Risk aggregation logic
├── API Routes
│   └── POST /sessions/{id}/frames
├── Webhooks
│   └── session.flagged event
└── Tests
```

### Phase 3: Gaze & Attention Tracking (Weeks 5-6)

```
Tasks:
├── Domain
│   ├── HeadPose value object
│   ├── GazeDirection value object
│   └── GazeAnalysisResult entity
├── Infrastructure
│   ├── IGazeTracker interface
│   └── MediaPipeGazeTracker implementation
├── Integration
│   └── Add to frame analysis pipeline
└── Tests
```

### Phase 4: Incident Management (Weeks 7-8)

```
Tasks:
├── Domain
│   ├── ProctorIncident entity
│   ├── IncidentEvidence entity
│   └── IncidentType/Severity enums
├── Repository
│   ├── IProctorIncidentRepository interface
│   └── PostgresIncidentRepository implementation
├── Use Cases
│   ├── CreateIncident
│   ├── ListIncidents
│   ├── ReviewIncident
│   └── GetSessionReport
├── Evidence Storage
│   └── S3 evidence storage
├── API Routes
│   └── /api/v1/proctor/incidents/*
├── Webhooks
│   └── incident.created event
└── Tests
```

### Phase 5: Object Detection (Weeks 9-10)

```
Tasks:
├── Domain
│   ├── DetectedObject value object
│   └── ObjectDetectionResult entity
├── Infrastructure
│   ├── IObjectDetector interface
│   └── YOLOObjectDetector implementation
├── Integration
│   └── Add to frame analysis pipeline
└── Tests
```

### Phase 6: Audio Analysis (Weeks 11-12)

```
Tasks:
├── Domain
│   └── AudioAnalysisResult entity
├── Infrastructure
│   ├── IAudioAnalyzer interface
│   └── WebRTCVADAudioAnalyzer implementation
├── Integration
│   └── Add to frame analysis pipeline
└── Tests
```

---

## 12. Validation Checklist

### Design Validation

- [ ] **Single Responsibility**: Each entity/service has one clear purpose
- [ ] **Open/Closed**: Extensible via interfaces, not modification
- [ ] **Liskov Substitution**: Implementations are interchangeable
- [ ] **Interface Segregation**: Focused interfaces per capability
- [ ] **Dependency Inversion**: Depend on abstractions, not concretions

### Architecture Validation

- [ ] Clean Architecture layers maintained
- [ ] Domain layer has no external dependencies
- [ ] Use cases orchestrate domain operations
- [ ] Infrastructure implements interfaces
- [ ] API layer is thin translation layer

### Security Validation

- [ ] All endpoints authenticated
- [ ] Rate limiting configured
- [ ] Input validation comprehensive
- [ ] SQL injection prevented (parameterized queries)
- [ ] XSS prevention in responses
- [ ] Sensitive data encrypted

### Privacy Validation

- [ ] Data minimization implemented
- [ ] Retention policies enforced
- [ ] Consent tracked
- [ ] Audit logging complete
- [ ] GDPR requirements met

### Performance Validation

- [ ] Frame analysis < 500ms p95
- [ ] API response < 200ms p95
- [ ] Supports 10K concurrent sessions
- [ ] Database queries optimized
- [ ] Caching strategy defined

---

## Appendix A: File Structure

```
app/
├── domain/
│   ├── entities/
│   │   ├── proctor_session.py      # NEW
│   │   ├── proctor_incident.py     # NEW
│   │   └── proctor_analysis.py     # NEW
│   └── interfaces/
│       ├── proctor_session_repository.py  # NEW
│       ├── proctor_incident_repository.py # NEW
│       ├── gaze_tracker.py         # NEW
│       ├── object_detector.py      # NEW
│       └── audio_analyzer.py       # NEW
├── application/
│   └── use_cases/
│       ├── proctor/                # NEW directory
│       │   ├── create_session.py
│       │   ├── start_session.py
│       │   ├── submit_frame.py
│       │   ├── end_session.py
│       │   ├── create_incident.py
│       │   ├── review_incident.py
│       │   └── get_session_report.py
│       └── ...
├── infrastructure/
│   ├── persistence/
│   │   └── repositories/
│   │       ├── postgres_session_repository.py  # NEW
│   │       └── postgres_incident_repository.py # NEW
│   ├── ml/
│   │   ├── gaze/                   # NEW directory
│   │   │   └── mediapipe_gaze_tracker.py
│   │   ├── detection/              # NEW directory
│   │   │   └── yolo_object_detector.py
│   │   └── audio/                  # NEW directory
│   │       └── vad_audio_analyzer.py
│   └── storage/
│       └── s3_evidence_storage.py  # NEW
├── api/
│   ├── routes/
│   │   └── proctor.py              # NEW
│   └── schemas/
│       └── proctor.py              # NEW
└── core/
    └── metrics/
        └── proctor_metrics.py      # NEW
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Baseline Embedding** | Reference face embedding captured at session start |
| **Frame** | Single image capture from webcam |
| **Gaze Direction** | Estimated direction where eyes are looking |
| **Head Pose** | 3D orientation of head (pitch, yaw, roll) |
| **Incident** | Detected suspicious event during session |
| **Liveness** | Verification that face is real, not photo/video |
| **Risk Score** | Aggregated suspicion level (0.0-1.0) |
| **Session** | Single proctored exam period |
| **Verification** | Confirming identity matches baseline |

---

**Document Status:** Ready for Review
**Next Steps:** Stakeholder approval → Implementation kickoff
