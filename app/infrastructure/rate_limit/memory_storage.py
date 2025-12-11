"""In-memory rate limit storage implementation."""

import logging
import time
from collections import defaultdict
from typing import Dict, Optional

from app.domain.interfaces.rate_limit_storage import IRateLimitStorage, RateLimitInfo

logger = logging.getLogger(__name__)


class InMemoryRateLimitStorage:
    """In-memory rate limit storage.

    Simple storage for single-instance deployments.
    Uses sliding window algorithm.
    """

    def __init__(self) -> None:
        """Initialize in-memory rate limit storage."""
        self._data: Dict[str, dict] = defaultdict(
            lambda: {"count": 0, "window_start": 0, "tier": "standard"}
        )
        logger.info("InMemoryRateLimitStorage initialized")

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
        current_time = int(time.time())
        entry = self._data[key]

        # Check if window has expired
        if current_time >= entry["window_start"] + window_seconds:
            # Reset window
            entry["count"] = 0
            entry["window_start"] = current_time

        # Increment count
        entry["count"] += 1

        # Calculate remaining
        remaining = max(0, limit - entry["count"])
        reset_at = entry["window_start"] + window_seconds

        return RateLimitInfo(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            tier=entry.get("tier", "standard"),
        )

    async def get(self, key: str) -> Optional[RateLimitInfo]:
        """Get current rate limit info without incrementing.

        Args:
            key: Unique key

        Returns:
            Rate limit info or None if not found
        """
        if key not in self._data:
            return None

        entry = self._data[key]

        # Default to 60 requests per minute
        limit = 60
        window_seconds = 60

        current_time = int(time.time())
        reset_at = entry["window_start"] + window_seconds

        # Check if window has expired
        if current_time >= reset_at:
            return RateLimitInfo(
                limit=limit,
                remaining=limit,
                reset_at=current_time + window_seconds,
                tier=entry.get("tier", "standard"),
            )

        remaining = max(0, limit - entry["count"])

        return RateLimitInfo(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            tier=entry.get("tier", "standard"),
        )

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Unique key to reset
        """
        if key in self._data:
            self._data[key]["count"] = 0
            self._data[key]["window_start"] = int(time.time())
            logger.debug(f"Rate limit reset for key: {key}")

    async def get_all_keys(self) -> list:
        """Get all tracked keys.

        Returns:
            List of all keys being tracked
        """
        return list(self._data.keys())

    def set_tier(self, key: str, tier: str) -> None:
        """Set rate limit tier for a key.

        Args:
            key: Unique key
            tier: Tier name (free, standard, premium, unlimited)
        """
        self._data[key]["tier"] = tier
        logger.debug(f"Set tier for {key}: {tier}")
