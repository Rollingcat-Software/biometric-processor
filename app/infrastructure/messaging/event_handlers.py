"""Event handlers for processing incoming biometric events.

This module contains handlers that react to events published by
the identity-core-api and other services.

Following Command Query Responsibility Segregation (CQRS):
- Handlers process events without returning values
- Side effects include logging, notifications, analytics
- Decoupled from the event publishers
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BiometricEventHandler:
    """Handler for biometric-related events.

    This class processes events related to biometric operations,
    performing side effects like logging, metrics, and notifications.

    Following Single Responsibility Principle:
    - Focused solely on event handling logic
    - Does not perform biometric operations directly
    """

    def __init__(self):
        """Initialize event handler."""
        self.processed_events = 0
        logger.info("Initialized BiometricEventHandler")

    async def handle_enrollment_requested(self, event: Dict[str, Any]) -> None:
        """Handle enrollment requested event from identity-core-api.

        This is triggered when a user initiates enrollment through the API.

        Args:
            event: Event data containing user_id and enrollment details
        """
        try:
            event_id = event.get("event_id")
            user_id = event.get("user_id")
            correlation_id = event.get("correlation_id")

            logger.info(
                f"Processing enrollment request: "
                f"user_id={user_id}, "
                f"correlation_id={correlation_id}, "
                f"event_id={event_id}"
            )

            # Here you would:
            # 1. Log to analytics system
            # 2. Update monitoring metrics
            # 3. Send notifications if needed

            self.processed_events += 1

            logger.debug(f"Successfully processed enrollment request event: {event_id}")

        except Exception as e:
            logger.error(f"Error handling enrollment requested event: {e}", exc_info=True)

    async def handle_enrollment_completed(self, event: Dict[str, Any]) -> None:
        """Handle enrollment completed event.

        This is triggered after successful face enrollment.

        Args:
            event: Event data containing enrollment results
        """
        try:
            event_id = event.get("event_id")
            user_id = event.get("user_id")
            face_id = event.get("face_id")
            quality_score = event.get("quality_score")
            processing_time = event.get("processing_time_ms")

            logger.info(
                f"Enrollment completed: "
                f"user_id={user_id}, "
                f"face_id={face_id}, "
                f"quality_score={quality_score}, "
                f"processing_time_ms={processing_time}"
            )

            # Here you would:
            # 1. Update user status in database
            # 2. Send success notification to user
            # 3. Log to analytics
            # 4. Update metrics dashboard

            self.processed_events += 1

            logger.debug(f"Successfully processed enrollment completed event: {event_id}")

        except Exception as e:
            logger.error(f"Error handling enrollment completed event: {e}", exc_info=True)

    async def handle_enrollment_failed(self, event: Dict[str, Any]) -> None:
        """Handle enrollment failed event.

        This is triggered when face enrollment fails.

        Args:
            event: Event data containing failure details
        """
        try:
            event_id = event.get("event_id")
            user_id = event.get("user_id")
            error_message = event.get("error_message")

            logger.warning(
                f"Enrollment failed: "
                f"user_id={user_id}, "
                f"error={error_message}, "
                f"event_id={event_id}"
            )

            # Here you would:
            # 1. Log error to monitoring system
            # 2. Send failure notification to user
            # 3. Increment error metrics
            # 4. Trigger retry logic if applicable

            self.processed_events += 1

        except Exception as e:
            logger.error(f"Error handling enrollment failed event: {e}", exc_info=True)

    async def handle_verification_requested(self, event: Dict[str, Any]) -> None:
        """Handle verification requested event from identity-core-api.

        This is triggered when a user attempts to verify their identity.

        Args:
            event: Event data containing verification details
        """
        try:
            event_id = event.get("event_id")
            user_id = event.get("user_id")
            face_id = event.get("face_id")

            logger.info(
                f"Processing verification request: "
                f"user_id={user_id}, "
                f"face_id={face_id}, "
                f"event_id={event_id}"
            )

            # Here you would:
            # 1. Log verification attempt
            # 2. Update rate limiting counters
            # 3. Check for suspicious patterns

            self.processed_events += 1

        except Exception as e:
            logger.error(f"Error handling verification requested event: {e}", exc_info=True)

    async def handle_verification_completed(self, event: Dict[str, Any]) -> None:
        """Handle verification completed event.

        This is triggered after face verification completes.

        Args:
            event: Event data containing verification results
        """
        try:
            event.get("event_id")
            user_id = event.get("user_id")
            is_match = event.get("is_match")
            similarity_score = event.get("similarity_score")
            liveness_score = event.get("liveness_score")
            processing_time = event.get("processing_time_ms")

            logger.info(
                f"Verification completed: "
                f"user_id={user_id}, "
                f"is_match={is_match}, "
                f"similarity={similarity_score}, "
                f"liveness={liveness_score}, "
                f"processing_time_ms={processing_time}"
            )

            # Here you would:
            # 1. Update authentication logs
            # 2. Send result notification
            # 3. Update security metrics
            # 4. Detect fraud patterns

            self.processed_events += 1

        except Exception as e:
            logger.error(f"Error handling verification completed event: {e}", exc_info=True)

    async def handle_verification_failed(self, event: Dict[str, Any]) -> None:
        """Handle verification failed event.

        This is triggered when verification fails.

        Args:
            event: Event data containing failure details
        """
        try:
            event_id = event.get("event_id")
            user_id = event.get("user_id")
            error_message = event.get("error_message")

            logger.warning(
                f"Verification failed: "
                f"user_id={user_id}, "
                f"error={error_message}, "
                f"event_id={event_id}"
            )

            # Here you would:
            # 1. Log security event
            # 2. Update fraud detection system
            # 3. Send failure notification
            # 4. Trigger account lockout if needed

            self.processed_events += 1

        except Exception as e:
            logger.error(f"Error handling verification failed event: {e}", exc_info=True)

    async def handle_liveness_check_completed(self, event: Dict[str, Any]) -> None:
        """Handle liveness check completed event.

        This is triggered after liveness detection completes.

        Args:
            event: Event data containing liveness check results
        """
        try:
            event.get("event_id")
            user_id = event.get("user_id")
            is_live = event.get("is_live")
            liveness_score = event.get("liveness_score")
            technique = event.get("technique")

            logger.info(
                f"Liveness check completed: "
                f"user_id={user_id}, "
                f"is_live={is_live}, "
                f"score={liveness_score}, "
                f"technique={technique}"
            )

            # Here you would:
            # 1. Log anti-spoofing metrics
            # 2. Update security dashboards
            # 3. Trigger alerts for suspected spoofing

            self.processed_events += 1

        except Exception as e:
            logger.error(f"Error handling liveness check completed event: {e}", exc_info=True)

    async def handle_quality_assessment_completed(self, event: Dict[str, Any]) -> None:
        """Handle quality assessment completed event.

        This is triggered after image quality assessment.

        Args:
            event: Event data containing quality assessment results
        """
        try:
            event.get("event_id")
            user_id = event.get("user_id")
            quality_score = event.get("quality_score")
            is_acceptable = event.get("is_acceptable")
            issues = event.get("issues", [])

            logger.info(
                f"Quality assessment completed: "
                f"user_id={user_id}, "
                f"score={quality_score}, "
                f"acceptable={is_acceptable}, "
                f"issues={issues}"
            )

            # Here you would:
            # 1. Log quality metrics
            # 2. Provide feedback to users
            # 3. Update ML model training data

            self.processed_events += 1

        except Exception as e:
            logger.error(
                f"Error handling quality assessment completed event: {e}", exc_info=True
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get event processing statistics.

        Returns:
            Dictionary containing handler statistics
        """
        return {
            "processed_events": self.processed_events,
            "handler_type": "BiometricEventHandler",
        }


class EventRouter:
    """Routes events to appropriate handlers based on event type.

    This class implements the Chain of Responsibility pattern,
    routing events to the correct handler method.

    Following Open/Closed Principle:
    - Easy to add new event types without modifying existing code
    """

    def __init__(self, handler: BiometricEventHandler):
        """Initialize event router.

        Args:
            handler: Event handler instance to route events to
        """
        self.handler = handler
        self._routing_map = {
            "enrollment.requested": handler.handle_enrollment_requested,
            "enrollment.completed": handler.handle_enrollment_completed,
            "enrollment.failed": handler.handle_enrollment_failed,
            "verification.requested": handler.handle_verification_requested,
            "verification.completed": handler.handle_verification_completed,
            "verification.failed": handler.handle_verification_failed,
            "liveness.check.completed": handler.handle_liveness_check_completed,
            "quality.assessment.completed": handler.handle_quality_assessment_completed,
        }
        logger.info("Initialized EventRouter")

    async def route(self, event: Dict[str, Any]) -> None:
        """Route event to appropriate handler.

        Args:
            event: Event data containing event_type field
        """
        event_type = event.get("event_type")

        if not event_type:
            logger.warning("Received event without event_type field")
            return

        handler_func = self._routing_map.get(event_type)

        if handler_func:
            await handler_func(event)
        else:
            logger.debug(f"No handler registered for event type: {event_type}")

    def register_handler(self, event_type: str, handler_func) -> None:
        """Register a new event handler.

        Args:
            event_type: Event type to handle
            handler_func: Handler function (async)
        """
        self._routing_map[event_type] = handler_func
        logger.info(f"Registered handler for event type: {event_type}")

    def unregister_handler(self, event_type: str) -> None:
        """Unregister an event handler.

        Args:
            event_type: Event type to unregister
        """
        self._routing_map.pop(event_type, None)
        logger.info(f"Unregistered handler for event type: {event_type}")
