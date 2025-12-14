"""Rate limit storage interface."""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class RateLimitInfo:
    """Rate limit information for a key.

    Attributes:
        limit: Maximum requests allowed
        remaining: Remaining requests in window
        reset_at: Unix timestamp when limit resets
        tier: Rate limit tier name
    """

    limit: int
    remaining: int
    reset_at: int
    tier: str


class IRateLimitStorage(Protocol):
    """Interface for rate limit storage.

    Implementations track request counts per key within time windows.
    """

    async def increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitInfo:
        """Increment request count and return current limit info.

        Args:
            key: Unique key (tenant_id or API key)
            limit: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            Current rate limit information
        """
        ...

    async def get(self, key: str) -> Optional[RateLimitInfo]:
        """Get current rate limit info without incrementing.

        Args:
            key: Unique key

        Returns:
            Rate limit info or None if not found
        """
        ...

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Unique key to reset
        """
        ...

    async def get_all_keys(self) -> list:
        """Get all tracked keys.

        Returns:
            List of all keys being tracked
        """
        ...
