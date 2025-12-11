"""Rate limit storage factory."""

import logging
from typing import Literal, Optional

from app.domain.interfaces.rate_limit_storage import IRateLimitStorage

logger = logging.getLogger(__name__)

StorageBackend = Literal["memory", "redis"]


class RateLimitStorageFactory:
    """Factory for creating rate limit storage instances.

    Follows Open/Closed Principle: Add new backends without modifying existing code.
    """

    @staticmethod
    def create(
        backend: StorageBackend = "memory",
        redis_url: Optional[str] = None,
        key_prefix: str = "rate_limit:",
    ) -> IRateLimitStorage:
        """Create rate limit storage instance.

        Args:
            backend: Storage backend type
            redis_url: Redis URL (required for redis backend)
            key_prefix: Prefix for Redis keys (only used with redis backend)

        Returns:
            IRateLimitStorage implementation

        Raises:
            ValueError: If unknown backend specified or redis_url missing
        """
        if backend == "memory":
            from app.infrastructure.rate_limit.memory_storage import (
                InMemoryRateLimitStorage,
            )

            logger.info("Creating InMemoryRateLimitStorage")
            return InMemoryRateLimitStorage()

        elif backend == "redis":
            if not redis_url:
                raise ValueError("redis_url is required for redis backend")

            from app.infrastructure.rate_limit.redis_storage import (
                RedisRateLimitStorage,
            )

            logger.info(f"Creating RedisRateLimitStorage with prefix: {key_prefix}")
            return RedisRateLimitStorage(redis_url=redis_url, key_prefix=key_prefix)

        raise ValueError(f"Unknown storage backend: {backend}")
