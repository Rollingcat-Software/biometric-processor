"""Auto-cleaning in-memory rate limit storage.

This module provides a rate limit storage implementation with:
- Automatic cleanup of expired entries via background task
- Maximum capacity with LRU eviction
- Thread-safe operations via asyncio.Lock

Following:
- Single Responsibility: Only handles rate limit storage
- Strategy Pattern: Implements IRateLimitStorage interface
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from app.domain.interfaces.rate_limit_storage import RateLimitInfo

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEntry:
    """Internal entry for rate limit tracking.

    Attributes:
        count: Number of requests in current window
        window_start: Unix timestamp when window started
        tier: Rate limit tier (free, standard, premium, unlimited)
        last_accessed: Unix timestamp of last access (for LRU)
    """

    count: int
    window_start: int
    tier: str
    last_accessed: float


class AutoCleaningMemoryStorage:
    """Memory storage with automatic expired entry cleanup.

    This implementation addresses unbounded memory growth in the basic
    InMemoryRateLimitStorage by:

    1. Background Cleanup Task: Periodically removes expired entries
    2. Capacity Limits: LRU eviction when at max capacity
    3. Thread Safety: asyncio.Lock for concurrent access

    Memory Management:
        - Max entries limit prevents unbounded growth
        - Expired entries removed on access and by background task
        - LRU eviction for capacity overflow

    Usage:
        storage = AutoCleaningMemoryStorage(
            max_entries=100000,
            cleanup_interval_seconds=60
        )

        # Start cleanup task (call during app startup)
        await storage.start_cleanup_task()

        # Use normally
        info = await storage.increment("user123", limit=60, window_seconds=60)

        # Stop cleanup task (call during app shutdown)
        await storage.stop_cleanup_task()

    Attributes:
        max_entries: Maximum number of entries before LRU eviction
        cleanup_interval_seconds: Seconds between cleanup runs
    """

    def __init__(
        self,
        max_entries: int = 100000,
        cleanup_interval_seconds: int = 60,
    ) -> None:
        """Initialize auto-cleaning storage.

        Args:
            max_entries: Maximum entries before LRU eviction
            cleanup_interval_seconds: Interval for background cleanup task

        Note:
            Call start_cleanup_task() after initialization to enable
            automatic cleanup.
        """
        self._max_entries = max_entries
        self._cleanup_interval = cleanup_interval_seconds

        # OrderedDict for LRU tracking
        self._data: OrderedDict[str, RateLimitEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False

        # Statistics
        self._total_cleanups = 0
        self._total_evictions = 0
        self._total_expired_removed = 0

        logger.info(
            f"AutoCleaningMemoryStorage initialized: max_entries={max_entries}, "
            f"cleanup_interval={cleanup_interval_seconds}s"
        )

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task.

        Call this during application startup (e.g., in lifespan manager).
        The task periodically removes expired entries to prevent memory growth.
        """
        if self._cleanup_task is not None:
            logger.warning("Cleanup task already running")
            return

        self._shutdown = False
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started rate limit cleanup task")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task.

        Call this during application shutdown for graceful cleanup.
        """
        if self._cleanup_task is None:
            return

        self._shutdown = True
        self._cleanup_task.cancel()

        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass

        self._cleanup_task = None
        logger.info("Stopped rate limit cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self._cleanup_interval)
                if not self._shutdown:
                    await self._cleanup_expired()
                    self._total_cleanups += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)

    async def _cleanup_expired(self, window_seconds: int = 60) -> int:
        """Remove all expired entries.

        Args:
            window_seconds: Default window size for expiration check

        Returns:
            Number of entries removed
        """
        current_time = int(time.time())
        removed = 0

        async with self._lock:
            # Find expired keys
            expired_keys = [
                key
                for key, entry in self._data.items()
                if current_time >= entry.window_start + window_seconds
            ]

            # Remove expired entries
            for key in expired_keys:
                del self._data[key]
                removed += 1

        if removed > 0:
            self._total_expired_removed += removed
            logger.debug(f"Cleaned up {removed} expired rate limit entries")

        return removed

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

        async with self._lock:
            if key in self._data:
                entry = self._data[key]

                # Check if window has expired
                if current_time >= entry.window_start + window_seconds:
                    # Reset window
                    entry.count = 0
                    entry.window_start = current_time

                # Increment count
                entry.count += 1
                entry.last_accessed = time.time()

                # Move to end for LRU
                self._data.move_to_end(key)
            else:
                # Evict LRU entries if at capacity
                while len(self._data) >= self._max_entries:
                    evicted_key = next(iter(self._data))
                    del self._data[evicted_key]
                    self._total_evictions += 1
                    logger.debug(f"Evicted LRU rate limit entry: {evicted_key}")

                # Create new entry
                entry = RateLimitEntry(
                    count=1,
                    window_start=current_time,
                    tier="standard",
                    last_accessed=time.time(),
                )
                self._data[key] = entry

            # Calculate remaining
            remaining = max(0, limit - entry.count)
            reset_at = entry.window_start + window_seconds

            return RateLimitInfo(
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                tier=entry.tier,
            )

    async def get(self, key: str) -> Optional[RateLimitInfo]:
        """Get current rate limit info without incrementing.

        Args:
            key: Unique key

        Returns:
            Rate limit info or None if not found
        """
        async with self._lock:
            if key not in self._data:
                return None

            entry = self._data[key]

            # Default window
            limit = 60
            window_seconds = 60

            current_time = int(time.time())
            reset_at = entry.window_start + window_seconds

            # Check if window has expired
            if current_time >= reset_at:
                return RateLimitInfo(
                    limit=limit,
                    remaining=limit,
                    reset_at=current_time + window_seconds,
                    tier=entry.tier,
                )

            remaining = max(0, limit - entry.count)

            return RateLimitInfo(
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                tier=entry.tier,
            )

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Unique key to reset
        """
        async with self._lock:
            if key in self._data:
                entry = self._data[key]
                entry.count = 0
                entry.window_start = int(time.time())
                entry.last_accessed = time.time()
                logger.debug(f"Rate limit reset for key: {key}")

    async def get_all_keys(self) -> list:
        """Get all tracked keys.

        Returns:
            List of all keys being tracked
        """
        async with self._lock:
            return list(self._data.keys())

    def set_tier(self, key: str, tier: str) -> None:
        """Set rate limit tier for a key.

        Args:
            key: Unique key
            tier: Tier name (free, standard, premium, unlimited)
        """
        if key in self._data:
            self._data[key].tier = tier
            logger.debug(f"Set tier for {key}: {tier}")

    def get_stats(self) -> dict:
        """Get storage statistics.

        Returns:
            Dictionary with usage statistics
        """
        return {
            "size": len(self._data),
            "max_entries": self._max_entries,
            "total_cleanups": self._total_cleanups,
            "total_evictions": self._total_evictions,
            "total_expired_removed": self._total_expired_removed,
            "cleanup_running": self._cleanup_task is not None and not self._shutdown,
            "utilization": len(self._data) / self._max_entries if self._max_entries > 0 else 0,
        }

    @property
    def max_entries(self) -> int:
        """Get maximum entries capacity."""
        return self._max_entries

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"AutoCleaningMemoryStorage("
            f"size={stats['size']}/{stats['max_entries']}, "
            f"cleanup_running={stats['cleanup_running']})"
        )
