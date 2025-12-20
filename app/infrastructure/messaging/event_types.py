"""Event type definitions for biometric processing.

This module defines all event types used in the biometric processing pipeline.
Events follow a consistent structure with timestamp, correlation IDs, and payload.

Following Domain-Driven Design:
- Events represent facts that have occurred in the system
- Immutable data structures (frozen dataclasses)
- Rich domain information in payloads
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class EventType(str, Enum):
    """Event type enumeration for type-safe event handling."""

    # Enrollment events
    ENROLLMENT_REQUESTED = "enrollment.requested"
    ENROLLMENT_STARTED = "enrollment.started"
    ENROLLMENT_COMPLETED = "enrollment.completed"
    ENROLLMENT_FAILED = "enrollment.failed"

    # Verification events
    VERIFICATION_REQUESTED = "verification.requested"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_COMPLETED = "verification.completed"
    VERIFICATION_FAILED = "verification.failed"

    # Liveness detection events
    LIVENESS_CHECK_REQUESTED = "liveness.check.requested"
    LIVENESS_CHECK_STARTED = "liveness.check.started"
    LIVENESS_CHECK_COMPLETED = "liveness.check.completed"
    LIVENESS_CHECK_FAILED = "liveness.check.failed"

    # Face search events
    FACE_SEARCH_REQUESTED = "face.search.requested"
    FACE_SEARCH_COMPLETED = "face.search.completed"
    FACE_SEARCH_FAILED = "face.search.failed"

    # Quality assessment events
    QUALITY_ASSESSMENT_COMPLETED = "quality.assessment.completed"
    QUALITY_ASSESSMENT_FAILED = "quality.assessment.failed"


class EventPriority(str, Enum):
    """Event priority levels for queue processing."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class BaseEvent:
    """Base event structure for all biometric events.

    Attributes:
        event_id: Unique identifier for this event instance
        event_type: Type of the event
        timestamp: When the event occurred (ISO 8601 format)
        correlation_id: ID to correlate related events across services
        user_id: ID of the user associated with this event
        priority: Processing priority of the event
        metadata: Additional contextual information
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: EventType = field(default=EventType.ENROLLMENT_REQUESTED)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "priority": self.priority.value,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class EnrollmentEvent(BaseEvent):
    """Event for biometric enrollment operations.

    Attributes:
        face_id: Unique identifier for the enrolled face
        image_url: URL or path to the face image
        quality_score: Quality assessment score (0-100)
        embedding_dimension: Dimension of the face embedding
        success: Whether the enrollment was successful
        error_message: Error details if enrollment failed
        processing_time_ms: Time taken to process (milliseconds)
    """

    face_id: Optional[str] = None
    image_url: Optional[str] = None
    quality_score: Optional[float] = None
    embedding_dimension: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "face_id": self.face_id,
                "image_url": self.image_url,
                "quality_score": self.quality_score,
                "embedding_dimension": self.embedding_dimension,
                "success": self.success,
                "error_message": self.error_message,
                "processing_time_ms": self.processing_time_ms,
            }
        )
        return base_dict


@dataclass(frozen=True)
class VerificationEvent(BaseEvent):
    """Event for biometric verification operations.

    Attributes:
        face_id: ID of the face being verified against
        is_match: Whether verification succeeded
        similarity_score: Similarity score (0-1)
        threshold: Threshold used for verification
        confidence: Confidence level of the match
        liveness_score: Liveness detection score if checked
        processing_time_ms: Time taken to process (milliseconds)
        error_message: Error details if verification failed
    """

    face_id: Optional[str] = None
    is_match: bool = False
    similarity_score: Optional[float] = None
    threshold: Optional[float] = None
    confidence: Optional[float] = None
    liveness_score: Optional[float] = None
    processing_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "face_id": self.face_id,
                "is_match": self.is_match,
                "similarity_score": self.similarity_score,
                "threshold": self.threshold,
                "confidence": self.confidence,
                "liveness_score": self.liveness_score,
                "processing_time_ms": self.processing_time_ms,
                "error_message": self.error_message,
            }
        )
        return base_dict


@dataclass(frozen=True)
class LivenessCheckEvent(BaseEvent):
    """Event for liveness detection operations.

    Attributes:
        is_live: Whether the face is determined to be live
        liveness_score: Liveness confidence score (0-100)
        technique: Liveness detection technique used
        spoofing_indicators: List of detected spoofing attempts
        blink_detected: Whether eye blink was detected
        smile_detected: Whether smile was detected
        processing_time_ms: Time taken to process (milliseconds)
        error_message: Error details if check failed
    """

    is_live: bool = False
    liveness_score: Optional[float] = None
    technique: Optional[str] = None
    spoofing_indicators: Optional[list] = field(default_factory=list)
    blink_detected: Optional[bool] = None
    smile_detected: Optional[bool] = None
    processing_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "is_live": self.is_live,
                "liveness_score": self.liveness_score,
                "technique": self.technique,
                "spoofing_indicators": self.spoofing_indicators or [],
                "blink_detected": self.blink_detected,
                "smile_detected": self.smile_detected,
                "processing_time_ms": self.processing_time_ms,
                "error_message": self.error_message,
            }
        )
        return base_dict


@dataclass(frozen=True)
class FaceSearchEvent(BaseEvent):
    """Event for face search operations.

    Attributes:
        matches_found: Number of matching faces found
        top_match_id: ID of the best matching face
        top_match_score: Similarity score of the best match
        search_radius: Search radius used
        processing_time_ms: Time taken to process (milliseconds)
        error_message: Error details if search failed
    """

    matches_found: int = 0
    top_match_id: Optional[str] = None
    top_match_score: Optional[float] = None
    search_radius: Optional[float] = None
    processing_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "matches_found": self.matches_found,
                "top_match_id": self.top_match_id,
                "top_match_score": self.top_match_score,
                "search_radius": self.search_radius,
                "processing_time_ms": self.processing_time_ms,
                "error_message": self.error_message,
            }
        )
        return base_dict


@dataclass(frozen=True)
class QualityAssessmentEvent(BaseEvent):
    """Event for image quality assessment.

    Attributes:
        quality_score: Overall quality score (0-100)
        blur_score: Blur detection score
        brightness_score: Brightness adequacy score
        face_size: Detected face size in pixels
        is_acceptable: Whether quality meets minimum requirements
        issues: List of quality issues detected
        processing_time_ms: Time taken to process (milliseconds)
        error_message: Error details if assessment failed
    """

    quality_score: Optional[float] = None
    blur_score: Optional[float] = None
    brightness_score: Optional[float] = None
    face_size: Optional[int] = None
    is_acceptable: bool = False
    issues: Optional[list] = field(default_factory=list)
    processing_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "quality_score": self.quality_score,
                "blur_score": self.blur_score,
                "brightness_score": self.brightness_score,
                "face_size": self.face_size,
                "is_acceptable": self.is_acceptable,
                "issues": self.issues or [],
                "processing_time_ms": self.processing_time_ms,
                "error_message": self.error_message,
            }
        )
        return base_dict
