"""Redis-based event bus implementation.

This adapter implements the IEventBus port using Redis Pub/Sub for
real-time event-driven communication between microservices.

Architecture:
- Implements IEventBus interface (port)
- Uses redis-py with async support (aioredis)
- Supports pub/sub and streams patterns
- Error handling and retry logic
- JSON serialization for events

Following SOLID principles:
- Single Responsibility: Only handles Redis event bus operations
- Open/Closed: Extensible without modifying core logic
- Dependency Inversion: Depends on IEventBus abstraction
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

import redis.asyncio as redis
from redis.asyncio.client import PubSub

from app.domain.interfaces.event_bus import IEventBus

logger = logging.getLogger(__name__)


class EventBusError(Exception):
    """Base exception for event bus operations."""

    pass


class RedisEventBus(IEventBus):
    """Redis-based implementation of the event bus.

    This adapter uses Redis Pub/Sub for lightweight, real-time messaging
    between the biometric processor and identity core API.

    Features:
    - Async/non-blocking operations
    - Automatic reconnection handling
    - JSON serialization/deserialization
    - Error handling and logging
    - Health checking

    Attributes:
        redis_url: Redis connection URL
        redis_client: Async Redis client
        pubsub: Redis pub/sub handler
        subscriptions: Active channel subscriptions
        retry_attempts: Number of retry attempts for failed operations
        retry_delay: Delay between retry attempts (seconds)
    """

    def __init__(
        self,
        redis_url: str,
        max_connections: int = 10,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        decode_responses: bool = True,
    ):
        """Initialize Redis event bus.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
            max_connections: Maximum number of connections in the pool
            retry_attempts: Number of retry attempts for failed operations
            retry_delay: Delay between retry attempts (seconds)
            decode_responses: Whether to decode responses to strings
        """
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.decode_responses = decode_responses

        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[PubSub] = None
        self.subscriptions: Dict[str, Callable] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._is_connected = False

        logger.info(f"Initialized Redis event bus with URL: {redis_url}")

    async def connect(self) -> None:
        """Establish connection to Redis.

        Creates connection pool and prepares pub/sub handler.
        This method is idempotent - safe to call multiple times.
        """
        if self._is_connected and self.redis_client:
            logger.debug("Redis client already connected")
            return

        try:
            # Create async Redis client with connection pool
            self.redis_client = redis.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=self.decode_responses,
                encoding="utf-8",
            )

            # Test connection
            await self.redis_client.ping()

            # Initialize pub/sub
            self.pubsub = self.redis_client.pubsub()

            self._is_connected = True
            logger.info("Successfully connected to Redis event bus")

        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise EventBusError(f"Redis connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Close connection to Redis.

        Cleans up resources and stops listener tasks.
        """
        if not self._is_connected:
            logger.debug("Redis client already disconnected")
            return

        try:
            # Stop listener task
            if self._listener_task and not self._listener_task.done():
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass

            # Unsubscribe from all channels
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()

            self._is_connected = False
            self.subscriptions.clear()

            logger.info("Disconnected from Redis event bus")

        except redis.RedisError as e:
            logger.error(f"Error during Redis disconnect: {e}")
            raise EventBusError(f"Redis disconnect failed: {e}") from e

    async def publish(
        self,
        channel: str,
        event: Dict[str, Any],
        priority: Optional[str] = None,
    ) -> bool:
        """Publish an event to a Redis channel.

        Args:
            channel: Channel name to publish to
            event: Event data (must be JSON-serializable)
            priority: Optional priority level (unused in pub/sub, useful for streams)

        Returns:
            True if published successfully, False otherwise

        Raises:
            EventBusError: If publishing fails after retries
        """
        if not self._is_connected or not self.redis_client:
            logger.error("Cannot publish - Redis client not connected")
            return False

        # Serialize event to JSON
        try:
            message = json.dumps(event, default=str)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize event: {e}")
            return False

        # Retry logic for publishing
        for attempt in range(self.retry_attempts):
            try:
                # Publish to Redis channel
                subscribers = await self.redis_client.publish(channel, message)

                logger.debug(
                    f"Published event to channel '{channel}' "
                    f"(event_type: {event.get('event_type')}, "
                    f"event_id: {event.get('event_id')}, "
                    f"subscribers: {subscribers})"
                )

                return True

            except redis.RedisError as e:
                logger.warning(
                    f"Failed to publish to channel '{channel}' "
                    f"(attempt {attempt + 1}/{self.retry_attempts}): {e}"
                )

                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to publish after {self.retry_attempts} attempts")
                    raise EventBusError(f"Publish failed: {e}") from e

        return False

    async def subscribe(
        self,
        channel: str,
        handler: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Subscribe to events on a Redis channel.

        Args:
            channel: Channel name to subscribe to
            handler: Async callback function to handle received events

        Raises:
            EventBusError: If subscription fails
        """
        if not self._is_connected or not self.pubsub:
            raise EventBusError("Cannot subscribe - Redis client not connected")

        try:
            # Subscribe to channel
            await self.pubsub.subscribe(channel)
            self.subscriptions[channel] = handler

            logger.info(f"Subscribed to channel: {channel}")

            # Start listener task if not already running
            if not self._listener_task or self._listener_task.done():
                self._listener_task = asyncio.create_task(self._listen_for_messages())

        except redis.RedisError as e:
            logger.error(f"Failed to subscribe to channel '{channel}': {e}")
            raise EventBusError(f"Subscribe failed: {e}") from e

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a Redis channel.

        Args:
            channel: Channel name to unsubscribe from
        """
        if not self._is_connected or not self.pubsub:
            logger.warning("Cannot unsubscribe - Redis client not connected")
            return

        try:
            await self.pubsub.unsubscribe(channel)
            self.subscriptions.pop(channel, None)

            logger.info(f"Unsubscribed from channel: {channel}")

        except redis.RedisError as e:
            logger.error(f"Failed to unsubscribe from channel '{channel}': {e}")

    async def _listen_for_messages(self) -> None:
        """Background task to listen for incoming messages.

        This coroutine runs continuously and dispatches messages
        to the appropriate handlers based on channel subscriptions.
        """
        if not self.pubsub:
            return

        logger.info("Started listening for Redis messages")

        try:
            async for message in self.pubsub.listen():
                # Filter out subscription confirmation messages
                if message["type"] != "message":
                    continue

                channel = message["channel"]
                data = message["data"]

                # Decode if necessary
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                # Deserialize JSON
                try:
                    event = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to deserialize message from '{channel}': {e}")
                    continue

                # Dispatch to handler
                handler = self.subscriptions.get(channel)
                if handler:
                    try:
                        # Call handler (async or sync)
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)

                        logger.debug(
                            f"Processed event from channel '{channel}' "
                            f"(event_type: {event.get('event_type')})"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error in event handler for channel '{channel}': {e}",
                            exc_info=True,
                        )

        except asyncio.CancelledError:
            logger.info("Message listener task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in message listener: {e}", exc_info=True)

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        if not self._is_connected or not self.redis_client:
            return False

        try:
            await self.redis_client.ping()
            return True
        except redis.RedisError:
            return False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
