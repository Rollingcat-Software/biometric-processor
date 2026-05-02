"""SQLAlchemy ORM models for the Biometric Processor database.

This module defines all database models that map to PostgreSQL tables.
These models are used by Alembic for migrations and can be used for
ORM-based operations.

Tables:
    - face_embeddings: Face embedding vectors with quality metadata
    - proctor_sessions: Proctoring session lifecycle tracking
    - proctor_incidents: Detected incidents during proctoring
    - incident_evidence: Evidence files attached to incidents
    - rate_limits: Rate limiting storage
    - api_keys: API key management
"""

from datetime import datetime
from typing import Any, Optional
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Enum definitions matching PostgreSQL enums
class SessionStatus(str, enum.Enum):
    """Proctoring session status states."""
    CREATED = "created"
    STARTED = "started"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FLAGGED = "flagged"


class IncidentType(str, enum.Enum):
    """Types of proctoring incidents."""
    FACE_NOT_DETECTED = "face_not_detected"
    MULTIPLE_FACES = "multiple_faces"
    GAZE_AWAY_PROLONGED = "gaze_away_prolonged"
    OBJECT_DETECTED = "object_detected"
    AUDIO_ANOMALY = "audio_anomaly"
    TAB_SWITCH = "tab_switch"
    SCREEN_SHARE_STOPPED = "screen_share_stopped"
    VERIFICATION_FAILED = "verification_failed"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    DEEPFAKE_DETECTED = "deepfake_detected"
    ENVIRONMENT_CHANGE = "environment_change"
    NETWORK_ISSUE = "network_issue"


class IncidentSeverity(str, enum.Enum):
    """Severity levels for incidents."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewAction(str, enum.Enum):
    """Review actions for incidents."""
    PENDING = "pending"
    DISMISSED = "dismissed"
    CONFIRMED = "confirmed"
    ESCALATED = "escalated"


class FaceEmbeddingModel(Base):
    """Face embedding storage model.

    Stores face embedding vectors along with quality metadata
    for face recognition operations.
    """
    __tablename__ = "face_embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    # GDPR P1.3 — canonical ciphertext (Fernet) of the embedding vector.
    # Nullable until backfill completes; will be promoted in a follow-up.
    embedding_ciphertext: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=512)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="facenet")
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_image_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<FaceEmbedding(id={self.id}, user_id={self.user_id}, quality={self.quality_score})>"


class ProctorSessionModel(Base):
    """Proctoring session model.

    Tracks the lifecycle of a proctoring session including
    verification attempts, risk scores, and session state.
    """
    __tablename__ = "proctor_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="created",
        index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    integrity_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    verification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_verifications: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    incidents: Mapped[list["ProctorIncidentModel"]] = relationship(
        "ProctorIncidentModel",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProctorSession(id={self.id}, exam={self.exam_id}, status={self.status})>"


class ProctorIncidentModel(Base):
    """Proctoring incident model.

    Records detected incidents during proctoring sessions
    with severity and review workflow support.
    """
    __tablename__ = "proctor_incidents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("proctor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="low", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    frame_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_contribution: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    review_action: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    session: Mapped["ProctorSessionModel"] = relationship(
        "ProctorSessionModel",
        back_populates="incidents"
    )
    evidence: Mapped[list["IncidentEvidenceModel"]] = relationship(
        "IncidentEvidenceModel",
        back_populates="incident",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProctorIncident(id={self.id}, type={self.incident_type}, severity={self.severity})>"


class IncidentEvidenceModel(Base):
    """Incident evidence model.

    Stores evidence files (screenshots, recordings)
    attached to proctoring incidents.
    """
    __tablename__ = "incident_evidence"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("proctor_incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    storage_bucket: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    incident: Mapped["ProctorIncidentModel"] = relationship(
        "ProctorIncidentModel",
        back_populates="evidence"
    )

    def __repr__(self) -> str:
        return f"<IncidentEvidence(id={self.id}, type={self.evidence_type})>"


class RateLimitModel(Base):
    """Rate limit storage model.

    Stores rate limiting counters with sliding window support.
    """
    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_start: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="standard", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<RateLimit(key={self.key}, count={self.count}, tier={self.tier})>"


class APIKeyModel(Base):
    """API key storage model.

    Stores API keys with hashed values, scopes, and usage tracking.
    Never stores plaintext keys - only hashed values.
    """
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="read,write")
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.key_prefix})>"
