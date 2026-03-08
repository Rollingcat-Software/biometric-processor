"""Base classes for domain events.

This module provides the foundational abstractions for domain-driven design events:
- DomainEvent: Represents something that happened in the domain
- DomainEventHandler: Processes domain events
- DomainEventPublisher: Publishes events to handlers

Design Patterns:
- Observer Pattern: Handlers observe events
- Publish-Subscribe: Decoupled communication
- Event Sourcing: Store events as source of truth
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Type, TypeVar
from uuid import UUID, uuid4

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for all domain events.

    Domain events are immutable records of something that happened in the domain.
    They are named in past tense and contain all relevant data.

    Design Principles:
    - Immutable (frozen): Events represent facts that cannot change
    - Past tense naming: FaceEnrolled, not EnrollFace
    - Rich with data: Contains everything needed to understand what happened
    - Timestamped: When did it happen
    - Identifiable: Unique ID for event tracing

    Example:
        @dataclass(frozen=True)
        class FaceEnrolledEvent(DomainEvent):
            user_id: str
            quality_score: float
            tenant_id: Optional[str] = None
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    event_version: str = "1.0"

    def get_event_name(self) -> str:
        """Get the name of this event.

        Returns:
            Event class name
        """
        return self.__class__.__name__

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.

        Returns:
            Dictionary representation of the event
        """
        return {
            "event_id": str(self.event_id),
            "event_name": self.get_event_name(),
            "occurred_at": self.occurred_at.isoformat(),
            "event_version": self.event_version,
            "data": {
                k: v for k, v in self.__dict__.items()
                if k not in ("event_id", "occurred_at", "event_version")
            }
        }


TEvent = TypeVar('TEvent', bound=DomainEvent)


class DomainEventHandler(ABC, Generic[TEvent]):
    """Base class for domain event handlers.

    Event handlers react to domain events and perform side effects.
    They should be idempotent (safe to run multiple times).

    Design Principles:
    - Single Responsibility: One handler per concern
    - Idempotent: Safe to run multiple times with same event
    - Async: Non-blocking event processing
    - Error Handling: Should not fail the main operation

    Example:
        class SendEnrollmentEmailHandler(DomainEventHandler[FaceEnrolledEvent]):
            def __init__(self, email_service: IEmailService):
                self._email_service = email_service

            async def handle(self, event: FaceEnrolledEvent) -> None:
                await self._email_service.send_enrollment_confirmation(
                    user_id=event.user_id
                )
    """

    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        """Handle the domain event.

        Args:
            event: The event to handle

        Note:
            Handlers should be idempotent and should not raise exceptions
            that would interrupt the main business flow.
        """
        pass

    def get_event_type(self) -> Type[TEvent]:
        """Get the event type this handler processes.

        Returns:
            Event class this handler processes
        """
        # Get the generic type parameter
        return self.__orig_bases__[0].__args__[0]  # type: ignore


class DomainEventPublisher:
    """Publisher for domain events.

    The event publisher routes events to their registered handlers.
    It supports multiple handlers per event type for flexible processing.

    Design Patterns:
    - Mediator: Centralizes event routing
    - Observer: Notifies handlers of events
    - Async: Non-blocking event propagation

    Benefits:
    - Loose coupling: Event producers don't know about handlers
    - Scalable: Easy to add new handlers
    - Testable: Can swap handlers for testing
    - Async: Event processing doesn't block main flow

    Example:
        # Setup
        publisher = DomainEventPublisher()
        publisher.subscribe(FaceEnrolledEvent, email_handler)
        publisher.subscribe(FaceEnrolledEvent, webhook_handler)

        # Publish event
        event = FaceEnrolledEvent(user_id="123", quality_score=95.5)
        await publisher.publish(event)
    """

    def __init__(self):
        """Initialize event publisher with empty handler registry."""
        self._handlers: Dict[Type[DomainEvent], List[DomainEventHandler]] = {}
        logger.info("DomainEventPublisher initialized")

    def subscribe(
        self,
        event_type: Type[TEvent],
        handler: DomainEventHandler[TEvent]
    ) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The event class to subscribe to
            handler: The handler to call when event is published

        Note:
            Multiple handlers can be subscribed to the same event type.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)
        logger.info(
            f"Subscribed handler {handler.__class__.__name__} "
            f"to event {event_type.__name__}"
        )

    def unsubscribe(
        self,
        event_type: Type[TEvent],
        handler: DomainEventHandler[TEvent]
    ) -> None:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The event class to unsubscribe from
            handler: The handler to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
            logger.info(
                f"Unsubscribed handler {handler.__class__.__name__} "
                f"from event {event_type.__name__}"
            )

    async def publish(self, event: TEvent) -> None:
        """Publish an event to all registered handlers.

        Args:
            event: The event to publish

        Note:
            Handlers are called sequentially. If a handler fails,
            the error is logged but other handlers are still called.
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug(f"No handlers registered for event: {event.get_event_name()}")
            return

        logger.info(
            f"Publishing event {event.get_event_name()} to {len(handlers)} handler(s)"
        )

        for handler in handlers:
            try:
                await handler.handle(event)
                logger.debug(
                    f"Handler {handler.__class__.__name__} "
                    f"processed event {event.get_event_name()}"
                )
            except Exception as e:
                # Log error but don't interrupt other handlers
                logger.error(
                    f"Handler {handler.__class__.__name__} failed "
                    f"for event {event.get_event_name()}: {str(e)}",
                    exc_info=True
                )

    def has_handlers(self, event_type: Type[DomainEvent]) -> bool:
        """Check if any handlers are registered for an event type.

        Args:
            event_type: The event class to check

        Returns:
            True if handlers are registered, False otherwise
        """
        return event_type in self._handlers and len(self._handlers[event_type]) > 0

    def get_handler_count(self, event_type: Type[DomainEvent]) -> int:
        """Get number of handlers registered for an event type.

        Args:
            event_type: The event class to check

        Returns:
            Number of registered handlers
        """
        return len(self._handlers.get(event_type, []))
