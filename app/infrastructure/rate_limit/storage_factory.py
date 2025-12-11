"""Rate limit storage factory."""

from typing import Literal, Optional

from app.domain.interfaces.rate_limit_storage import IRateLimitStorage

StorageBackend = Literal["memory", "redis"]


class RateLimitStorageFactory:
    """Factory for creating rate limit storage instances.

    Follows Open/Closed Principle: Add new backends without modifying existing code.
    """

    @staticmethod
    def create(
        backend: StorageBackend = "memory",
        redis_url: Optional[str] = None,
    ) -> IRateLimitStorage:
        """Create rate limit storage instance.

        Args:
            backend: Storage backend type
            redis_url: Redis URL (required for redis backend)

        Returns:
            IRateLimitStorage implementation

        Raises:
            ValueError: If unknown backend specified
        """
        if backend == "memory":
            from app.infrastructure.rate_limit.memory_storage import (
                InMemoryRateLimitStorage,
            )

            return InMemoryRateLimitStorage()

        elif backend == "redis":
            # Placeholder for Redis implementation
            raise NotImplementedError("Redis rate limit storage not yet implemented")

        raise ValueError(f"Unknown storage backend: {backend}")
