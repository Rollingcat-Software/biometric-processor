"""Interface for ML operation caching.

This module defines the protocol for cache implementations used
with ML operations like embedding extraction.

Following:
- Interface Segregation: Focused interface for caching operations
- Dependency Inversion: Depend on abstraction, not concrete cache
"""

from dataclasses import dataclass
from typing import Optional, Protocol, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring.

    Attributes:
        hits: Number of successful cache hits
        misses: Number of cache misses
        size: Current number of entries
        max_size: Maximum capacity
        evictions: Number of entries evicted due to capacity
    """

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


class IMLCache(Protocol[K, V]):
    """Protocol for ML operation caching.

    This interface defines the contract for cache implementations
    used with ML operations. Implementations must be thread-safe.

    Type Parameters:
        K: Key type (typically str for hash keys)
        V: Value type (typically np.ndarray for embeddings)

    Usage:
        def process_with_cache(cache: IMLCache[str, np.ndarray], key: str) -> np.ndarray:
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = expensive_computation()
            cache.put(key, result)
            return result
    """

    def get(self, key: K) -> Optional[V]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired

        Note:
            Implementation should update access time for LRU tracking.
        """
        ...

    def put(self, key: K, value: V) -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache

        Note:
            Implementation should handle capacity limits and eviction.
        """
        ...

    def invalidate(self, key: K) -> bool:
        """Remove a specific key from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if key was present and removed, False otherwise
        """
        ...

    def clear(self) -> None:
        """Remove all entries from cache."""
        ...

    def stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with current statistics
        """
        ...

    @property
    def size(self) -> int:
        """Get current number of entries."""
        ...

    @property
    def max_size(self) -> int:
        """Get maximum cache size."""
        ...
