"""Thread-safe LRU cache implementation with TTL support.

This module provides a generic LRU (Least Recently Used) cache that is
thread-safe and supports optional time-to-live for entries.

Following:
- Single Responsibility: Only handles caching logic
- Interface Segregation: Implements IMLCache protocol
"""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int
    misses: int
    size: int
    max_size: int
    evictions: int

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": self.size,
            "max_size": self.max_size,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
        }


@dataclass
class _CacheEntry(Generic[V]):
    """Internal cache entry with timestamp."""

    value: V
    created_at: float
    last_accessed: float


class ThreadSafeLRUCache(Generic[K, V]):
    """Thread-safe LRU cache with optional TTL support.

    This cache implementation provides:
    - O(1) get/put operations (amortized)
    - LRU eviction when at capacity
    - Optional TTL for automatic entry expiration
    - Thread-safe operations via threading.Lock
    - Statistics for monitoring (hits, misses, evictions)

    Thread Safety:
        All public methods are protected by a lock. The lock is held
        for the minimum duration necessary.

    Usage:
        cache = ThreadSafeLRUCache[str, np.ndarray](max_size=1000, ttl_seconds=3600)

        # Store embedding
        cache.put("image_hash_123", embedding_vector)

        # Retrieve (returns None if not found or expired)
        cached = cache.get("image_hash_123")

        # Get statistics
        stats = cache.stats()
        print(f"Hit rate: {stats.hit_rate:.2%}")

    Attributes:
        max_size: Maximum number of entries before eviction
        ttl_seconds: Optional time-to-live in seconds (None = no expiration)
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Initialize LRU cache.

        Args:
            max_size: Maximum entries before LRU eviction starts
            ttl_seconds: Optional TTL in seconds. None means no expiration.

        Raises:
            ValueError: If max_size < 1
        """
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")

        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[K, _CacheEntry[V]] = OrderedDict()
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.info(
            f"ThreadSafeLRUCache initialized: max_size={max_size}, "
            f"ttl_seconds={ttl_seconds}"
        )

    def get(self, key: K) -> Optional[V]:
        """Get value from cache.

        Moves the accessed entry to the end (most recently used).
        Returns None if key not found or entry has expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            # Check TTL expiration
            if self._ttl_seconds is not None:
                age = time.time() - entry.created_at
                if age > self._ttl_seconds:
                    # Entry expired, remove it
                    del self._cache[key]
                    self._misses += 1
                    return None

            # Update access time and move to end (most recently used)
            entry.last_accessed = time.time()
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.value

    def put(self, key: K, value: V) -> None:
        """Store value in cache.

        If key already exists, updates the value and moves to end.
        If at capacity, evicts the least recently used entry.

        Args:
            key: Cache key
            value: Value to cache
        """
        current_time = time.time()

        with self._lock:
            if key in self._cache:
                # Update existing entry
                self._cache[key] = _CacheEntry(
                    value=value,
                    created_at=current_time,
                    last_accessed=current_time,
                )
                self._cache.move_to_end(key)
            else:
                # Evict if at capacity
                while len(self._cache) >= self._max_size:
                    # Remove oldest (first) entry
                    evicted_key = next(iter(self._cache))
                    del self._cache[evicted_key]
                    self._evictions += 1

                # Add new entry
                self._cache[key] = _CacheEntry(
                    value=value,
                    created_at=current_time,
                    last_accessed=current_time,
                )

    def invalidate(self, key: K) -> bool:
        """Remove a specific key from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if key was present and removed, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Remove all entries from cache."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with current statistics
        """
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._cache),
                max_size=self._max_size,
                evictions=self._evictions,
            )

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        This is called automatically on get(), but can be called
        explicitly for batch cleanup.

        Returns:
            Number of entries removed
        """
        if self._ttl_seconds is None:
            return 0

        current_time = time.time()
        removed = 0

        with self._lock:
            # Build list of expired keys (can't modify dict while iterating)
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if (current_time - entry.created_at) > self._ttl_seconds
            ]

            for key in expired_keys:
                del self._cache[key]
                removed += 1

        if removed > 0:
            logger.debug(f"Cleaned up {removed} expired cache entries")

        return removed

    @property
    def size(self) -> int:
        """Get current number of entries."""
        with self._lock:
            return len(self._cache)

    @property
    def max_size(self) -> int:
        """Get maximum cache size."""
        return self._max_size

    def __len__(self) -> int:
        """Get current number of entries."""
        return self.size

    def __contains__(self, key: K) -> bool:
        """Check if key exists (without updating access time)."""
        with self._lock:
            return key in self._cache

    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"ThreadSafeLRUCache(size={stats.size}/{stats.max_size}, "
            f"hit_rate={stats.hit_rate:.2%})"
        )
