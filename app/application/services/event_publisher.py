"""Event publishing service for use cases.

This service provides a high-level API for publishing events from use cases
without coupling them directly to the event bus implementation.

Following Facade Pattern:
- Simplifies event publishing for use cases
- Provides a clean interface for event publication
- Handles serialization and error handling
"""

import logging
from typing import Optional

from app.domain.interfaces.event_bus import IEventBus
from app.infrastructure.messaging.event_types import (
    EnrollmentEvent,
    EventPriority,
    EventType,
    LivenessCheckEvent,
    QualityAssessmentEvent,
    VerificationEvent,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """Service for publishing biometric events to the event bus.

    This service acts as a facade between use cases and the event bus,
    providing convenient methods for publishing domain events.

    Following Single Responsibility Principle:
    - Only concerned with event publishing
    - Does not contain business logic
    """

    def __init__(self, event_bus: Optional[IEventBus] = None):
        """Initialize event publisher.

        Args:
            event_bus: Event bus implementation (optional for disabled scenarios)
        """
        self.event_bus = event_bus
        self._enabled = event_bus is not None
        logger.info(f"EventPublisher initialized (enabled={self._enabled})")

    async def publish_enrollment_started(
        self,
        user_id: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish enrollment started event.

        Args:
            user_id: ID of the user being enrolled
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = EnrollmentEvent(
            event_type=EventType.ENROLLMENT_STARTED,
            user_id=user_id,
            correlation_id=correlation_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.enrollment",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish enrollment started event: {e}")
            return False

    async def publish_enrollment_completed(
        self,
        user_id: str,
        face_id: str,
        quality_score: float,
        embedding_dimension: int,
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish enrollment completed event.

        Args:
            user_id: ID of the user enrolled
            face_id: ID of the enrolled face
            quality_score: Quality score of the image
            embedding_dimension: Dimension of the face embedding
            processing_time_ms: Time taken to process
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = EnrollmentEvent(
            event_type=EventType.ENROLLMENT_COMPLETED,
            user_id=user_id,
            face_id=face_id,
            quality_score=quality_score,
            embedding_dimension=embedding_dimension,
            success=True,
            processing_time_ms=processing_time_ms,
            correlation_id=correlation_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.enrollment",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish enrollment completed event: {e}")
            return False

    async def publish_enrollment_failed(
        self,
        user_id: str,
        error_message: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish enrollment failed event.

        Args:
            user_id: ID of the user
            error_message: Error description
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = EnrollmentEvent(
            event_type=EventType.ENROLLMENT_FAILED,
            user_id=user_id,
            success=False,
            error_message=error_message,
            correlation_id=correlation_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.enrollment",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish enrollment failed event: {e}")
            return False

    async def publish_verification_started(
        self,
        user_id: str,
        face_id: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish verification started event.

        Args:
            user_id: ID of the user being verified
            face_id: ID of the face to verify against
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = VerificationEvent(
            event_type=EventType.VERIFICATION_STARTED,
            user_id=user_id,
            face_id=face_id,
            correlation_id=correlation_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.verification",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish verification started event: {e}")
            return False

    async def publish_verification_completed(
        self,
        user_id: str,
        face_id: str,
        is_match: bool,
        similarity_score: float,
        threshold: float,
        confidence: float,
        liveness_score: Optional[float],
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish verification completed event.

        Args:
            user_id: ID of the user
            face_id: ID of the face verified against
            is_match: Whether verification succeeded
            similarity_score: Similarity score
            threshold: Threshold used
            confidence: Confidence level
            liveness_score: Liveness score if checked
            processing_time_ms: Time taken to process
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = VerificationEvent(
            event_type=EventType.VERIFICATION_COMPLETED,
            user_id=user_id,
            face_id=face_id,
            is_match=is_match,
            similarity_score=similarity_score,
            threshold=threshold,
            confidence=confidence,
            liveness_score=liveness_score,
            processing_time_ms=processing_time_ms,
            correlation_id=correlation_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.verification",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish verification completed event: {e}")
            return False

    async def publish_verification_failed(
        self,
        user_id: str,
        face_id: str,
        error_message: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish verification failed event.

        Args:
            user_id: ID of the user
            face_id: ID of the face
            error_message: Error description
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = VerificationEvent(
            event_type=EventType.VERIFICATION_FAILED,
            user_id=user_id,
            face_id=face_id,
            error_message=error_message,
            correlation_id=correlation_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.verification",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish verification failed event: {e}")
            return False

    async def publish_liveness_check_completed(
        self,
        user_id: str,
        is_live: bool,
        liveness_score: float,
        technique: str,
        spoofing_indicators: Optional[list],
        blink_detected: Optional[bool],
        smile_detected: Optional[bool],
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish liveness check completed event.

        Args:
            user_id: ID of the user
            is_live: Whether face is determined to be live
            liveness_score: Liveness confidence score
            technique: Technique used for detection
            spoofing_indicators: List of detected spoofing attempts
            blink_detected: Whether blink was detected
            smile_detected: Whether smile was detected
            processing_time_ms: Time taken to process
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = LivenessCheckEvent(
            event_type=EventType.LIVENESS_CHECK_COMPLETED,
            user_id=user_id,
            is_live=is_live,
            liveness_score=liveness_score,
            technique=technique,
            spoofing_indicators=spoofing_indicators,
            blink_detected=blink_detected,
            smile_detected=smile_detected,
            processing_time_ms=processing_time_ms,
            correlation_id=correlation_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.liveness",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish liveness check completed event: {e}")
            return False

    async def publish_quality_assessment_completed(
        self,
        user_id: str,
        quality_score: float,
        blur_score: Optional[float],
        brightness_score: Optional[float],
        face_size: Optional[int],
        is_acceptable: bool,
        issues: Optional[list],
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Publish quality assessment completed event.

        Args:
            user_id: ID of the user
            quality_score: Overall quality score
            blur_score: Blur detection score
            brightness_score: Brightness score
            face_size: Detected face size
            is_acceptable: Whether quality meets requirements
            issues: List of quality issues
            processing_time_ms: Time taken to process
            correlation_id: ID to correlate related events
            metadata: Additional contextual information

        Returns:
            True if published successfully, False otherwise
        """
        if not self._enabled or not self.event_bus:
            return False

        event = QualityAssessmentEvent(
            event_type=EventType.QUALITY_ASSESSMENT_COMPLETED,
            user_id=user_id,
            quality_score=quality_score,
            blur_score=blur_score,
            brightness_score=brightness_score,
            face_size=face_size,
            is_acceptable=is_acceptable,
            issues=issues,
            processing_time_ms=processing_time_ms,
            correlation_id=correlation_id,
            priority=EventPriority.LOW,
            metadata=metadata or {},
        )

        try:
            return await self.event_bus.publish(
                channel="biometric.quality",
                event=event.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to publish quality assessment completed event: {e}")
            return False
