"""Biometric domain events.

This module contains domain events for the biometric processing system.
Events are named in past tense and represent facts about what happened.
"""

from dataclasses import dataclass
from typing import List, Optional

from app.domain.events.base import DomainEvent


# ============================================================================
# Enrollment Events
# ============================================================================

@dataclass(frozen=True)
class FaceEnrolledEvent(DomainEvent):
    """Event raised when a face is successfully enrolled.

    This event indicates that a user's face has been registered
    in the biometric system.

    Attributes:
        user_id: Unique identifier for the user
        quality_score: Quality score of the enrolled face (0-100)
        embedding_dimension: Dimensionality of the face embedding
        tenant_id: Optional tenant identifier for multi-tenancy
    """

    user_id: str
    quality_score: float
    embedding_dimension: int
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class MultiImageEnrollmentCompletedEvent(DomainEvent):
    """Event raised when multi-image enrollment is completed.

    This event indicates that a user's face has been enrolled using
    multiple images with template fusion.

    Attributes:
        user_id: Unique identifier for the user
        images_processed: Number of images successfully processed
        fused_quality_score: Quality score of the fused template
        average_quality_score: Average quality across all images
        individual_quality_scores: List of individual image quality scores
        fusion_strategy: Strategy used for embedding fusion
        tenant_id: Optional tenant identifier for multi-tenancy
    """

    user_id: str
    images_processed: int
    fused_quality_score: float
    average_quality_score: float
    individual_quality_scores: List[float]
    fusion_strategy: str
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class EnrollmentFailedEvent(DomainEvent):
    """Event raised when enrollment fails.

    This event indicates that an enrollment attempt failed,
    typically due to quality issues or face detection failures.

    Attributes:
        user_id: Unique identifier for the user
        reason: Reason for enrollment failure
        error_code: Error code for categorization
        tenant_id: Optional tenant identifier for multi-tenancy
    """

    user_id: str
    reason: str
    error_code: str
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class EnrollmentDeletedEvent(DomainEvent):
    """Event raised when an enrollment is deleted.

    This event indicates that a user's biometric data has been
    removed from the system.

    Attributes:
        user_id: Unique identifier for the user
        tenant_id: Optional tenant identifier for multi-tenancy
        reason: Reason for deletion (e.g., GDPR, account closure)
    """

    user_id: str
    tenant_id: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class EnrollmentUpdatedEvent(DomainEvent):
    """Event raised when an enrollment is updated.

    This event indicates that a user's biometric template has been
    replaced with a new one.

    Attributes:
        user_id: Unique identifier for the user
        old_quality_score: Quality score of the previous enrollment
        new_quality_score: Quality score of the new enrollment
        tenant_id: Optional tenant identifier for multi-tenancy
    """

    user_id: str
    old_quality_score: float
    new_quality_score: float
    tenant_id: Optional[str] = None


# ============================================================================
# Verification Events
# ============================================================================

@dataclass(frozen=True)
class FaceVerifiedEvent(DomainEvent):
    """Event raised when a face is successfully verified.

    This event indicates that a face verification (1:1 match)
    was successful.

    Attributes:
        user_id: Unique identifier for the user
        similarity_score: Similarity score (0-1, higher is better)
        threshold: Verification threshold used
        verified: Whether verification passed
        tenant_id: Optional tenant identifier for multi-tenancy
    """

    user_id: str
    similarity_score: float
    threshold: float
    verified: bool
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class FaceSearchCompletedEvent(DomainEvent):
    """Event raised when a face search (1:N) is completed.

    This event indicates that a face identification search
    has been performed.

    Attributes:
        matches_found: Number of matches found
        top_match_user_id: User ID of the top match (if any)
        top_match_score: Similarity score of the top match
        threshold: Search threshold used
        tenant_id: Optional tenant identifier for multi-tenancy
    """

    matches_found: int
    top_match_user_id: Optional[str] = None
    top_match_score: Optional[float] = None
    threshold: float = 0.0
    tenant_id: Optional[str] = None


# ============================================================================
# Liveness Events
# ============================================================================

@dataclass(frozen=True)
class LivenessCheckCompletedEvent(DomainEvent):
    """Event raised when a liveness check is completed.

    This event indicates that a liveness detection check
    has been performed.

    Attributes:
        is_live: Whether the face is determined to be live
        confidence: Confidence score (0-100)
        liveness_score: Raw liveness score
        method: Liveness detection method used (passive, active, combined)
        checks_performed: List of checks performed (texture, blink, smile, etc.)
    """

    is_live: bool
    confidence: float
    liveness_score: float
    method: str
    checks_performed: List[str]


# ============================================================================
# Proctoring Events
# ============================================================================

@dataclass(frozen=True)
class ProctorSessionStartedEvent(DomainEvent):
    """Event raised when a proctoring session starts.

    Attributes:
        session_id: Unique session identifier
        user_id: User being proctored
        exam_id: Exam/assessment identifier
        tenant_id: Optional tenant identifier
    """

    session_id: str
    user_id: str
    exam_id: str
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class ProctorIncidentDetectedEvent(DomainEvent):
    """Event raised when a proctoring incident is detected.

    Attributes:
        session_id: Session where incident occurred
        incident_type: Type of incident (face_not_detected, multiple_faces, etc.)
        severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
        description: Human-readable description
        risk_score: Updated risk score after incident
        tenant_id: Optional tenant identifier
    """

    session_id: str
    incident_type: str
    severity: str
    description: str
    risk_score: float
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class ProctorSessionEndedEvent(DomainEvent):
    """Event raised when a proctoring session ends.

    Attributes:
        session_id: Session identifier
        user_id: User who was proctored
        final_risk_score: Final risk assessment score
        incidents_count: Total number of incidents
        session_duration: Duration in seconds
        termination_reason: Reason for session end
        tenant_id: Optional tenant identifier
    """

    session_id: str
    user_id: str
    final_risk_score: float
    incidents_count: int
    session_duration: int
    termination_reason: str
    tenant_id: Optional[str] = None


# ============================================================================
# Quality Events
# ============================================================================

@dataclass(frozen=True)
class PoorImageQualityDetectedEvent(DomainEvent):
    """Event raised when poor image quality is detected.

    This event can be used for analytics and system monitoring.

    Attributes:
        quality_score: Overall quality score
        issues: List of quality issues detected (blur, small_face, etc.)
        user_id: Optional user identifier if known
        tenant_id: Optional tenant identifier
    """

    quality_score: float
    issues: List[str]
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
