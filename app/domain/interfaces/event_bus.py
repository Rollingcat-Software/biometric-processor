"""Event bus port (interface) for messaging infrastructure.

This defines the contract for event publishing and subscription
following Hexagonal Architecture principles.

Port Pattern:
- Domain layer defines WHAT the system needs (interface)
- Infrastructure layer defines HOW it's implemented (adapter)
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class IEventBus(ABC):
    """Event bus interface for pub/sub messaging.

    This port defines the contract for publishing and subscribing to events
    in an async, non-blocking manner.

    Following Interface Segregation Principle:
    - Minimal interface focused on core event bus operations
    - Implementers can add additional features as needed
    """

    @abstractmethod
    async def publish(
        self,
        channel: str,
        event: Dict[str, Any],
        priority: Optional[str] = None,
    ) -> bool:
        """Publish an event to a channel.

        Args:
            channel: Channel/topic name to publish to
            event: Event data (must be JSON-serializable)
            priority: Optional priority level for the event

        Returns:
            True if published successfully, False otherwise

        Raises:
            EventBusError: If publishing fails critically
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        channel: str,
        handler: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Subscribe to events on a channel.

        Args:
            channel: Channel/topic name to subscribe to
            handler: Async callback function to handle received events

        Raises:
            EventBusError: If subscription fails critically
        """
        pass

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: Channel/topic name to unsubscribe from
        """
        pass

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the messaging backend.

        Should be idempotent - safe to call multiple times.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the messaging backend.

        Should cleanup resources and pending operations.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the event bus is healthy and ready.

        Returns:
            True if healthy, False otherwise
        """
        pass
