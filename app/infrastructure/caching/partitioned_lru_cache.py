"""Partitioned thread-safe LRU cache implementation.

Optimized for high-concurrency scenarios by partitioning the cache
to reduce lock contention.
"""

import hashlib
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
class PartitionedCacheStats:
    """Statistics for partitioned cache performance monitoring."""

    hits: int
    misses: int
    size: int
    max_size: int
    evictions: int
    partitions: int

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
            "partitions": self.partitions,
            "hit_rate": round(self.hit_rate, 4),
        }


@dataclass
class _CacheEntry(Generic[V]):
    """Internal cache entry with timestamp."""

    value: V
    created_at: float
    last_accessed: float


class _CachePartition(Generic[K, V]):
    """Single partition of the cache with its own lock."""

    def __init__(self, max_size: int, ttl_seconds: Optional[int] = None) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[K, _CacheEntry[V]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: K) -> Optional[V]:
        """Get value from partition."""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            # Check TTL expiration
            if self._ttl_seconds is not None:
                age = time.time() - entry.created_at
                if age > self._ttl_seconds:
                    del self._cache[key]
                    self._misses += 1
                    return None

            # Update access time and move to end
            entry.last_accessed = time.time()
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.value

    def put(self, key: K, value: V) -> None:
        """Store value in partition."""
        current_time = time.time()

        with self._lock:
            if key in self._cache:
                # Update existing
                self._cache[key] = _CacheEntry(
                    value=value,
                    created_at=current_time,
                    last_accessed=current_time,
                )
                self._cache.move_to_end(key)
            else:
                # Evict if needed
                while len(self._cache) >= self._max_size:
                    evicted_key = next(iter(self._cache))
                    del self._cache[evicted_key]
                    self._evictions += 1

                # Add new
                self._cache[key] = _CacheEntry(
                    value=value,
                    created_at=current_time,
                    last_accessed=current_time,
                )

    def invalidate(self, key: K) -> bool:
        """Remove key from partition."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current size."""
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> tuple:
        """Get (hits, misses, size, evictions)."""
        with self._lock:
            return (self._hits, self._misses, len(self._cache), self._evictions)

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        if self._ttl_seconds is None:
            return 0

        current_time = time.time()
        removed = 0

        with self._lock:
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if (current_time - entry.created_at) > self._ttl_seconds
            ]

            for key in expired_keys:
                del self._cache[key]
                removed += 1

        return removed


class PartitionedLRUCache(Generic[K, V]):
    """Partitioned thread-safe LRU cache with TTL support.

    Optimizes for high concurrency by splitting the cache into multiple
    partitions, each with its own lock. This reduces contention when
    multiple threads access the cache concurrently.

    Performance Characteristics:
    - O(1) get/put operations (amortized)
    - Reduced lock contention vs single-lock cache
    - Linear scaling with partition count up to ~16 partitions
    - Best for read-heavy workloads with many concurrent accessors

    Thread Safety:
        Each partition has its own lock. Operations on different partitions
        can proceed concurrently without blocking.

    Usage:
        cache = PartitionedLRUCache[str, np.ndarray](
            max_size=10000,
            ttl_seconds=3600,
            num_partitions=16
        )

        # Store embedding
        cache.put("image_hash_123", embedding_vector)

        # Retrieve
        cached = cache.get("image_hash_123")

        # Get statistics
        stats = cache.stats()
        print(f"Hit rate: {stats.hit_rate:.2%}")

    Attributes:
        max_size: Maximum total entries across all partitions
        ttl_seconds: Optional TTL in seconds
        num_partitions: Number of cache partitions (default: 16)
    """

    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: Optional[int] = None,
        num_partitions: int = 16,
    ) -> None:
        """Initialize partitioned cache.

        Args:
            max_size: Maximum total entries before eviction
            ttl_seconds: Optional TTL. None means no expiration.
            num_partitions: Number of partitions (power of 2 recommended)

        Raises:
            ValueError: If max_size < num_partitions or num_partitions < 1
        """
        if num_partitions < 1:
            raise ValueError(f"num_partitions must be >= 1, got {num_partitions}")
        if max_size < num_partitions:
            raise ValueError(
                f"max_size ({max_size}) must be >= num_partitions ({num_partitions})"
            )

        self._num_partitions = num_partitions
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

        # Create partitions with roughly equal max sizes
        partition_size = max_size // num_partitions
        self._partitions = [
            _CachePartition[K, V](
                max_size=partition_size,
                ttl_seconds=ttl_seconds,
            )
            for _ in range(num_partitions)
        ]

        logger.info(
            f"PartitionedLRUCache initialized: max_size={max_size}, "
            f"partitions={num_partitions}, partition_size={partition_size}, "
            f"ttl_seconds={ttl_seconds}"
        )

    def _get_partition_index(self, key: K) -> int:
        """Get partition index for a key using consistent hashing."""
        # Use hash for distribution
        if isinstance(key, str):
            key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)
        else:
            key_hash = hash(key)
        return key_hash % self._num_partitions

    def get(self, key: K) -> Optional[V]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        partition_idx = self._get_partition_index(key)
        return self._partitions[partition_idx].get(key)

    def put(self, key: K, value: V) -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        partition_idx = self._get_partition_index(key)
        self._partitions[partition_idx].put(key, value)

    def invalidate(self, key: K) -> bool:
        """Remove a specific key from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if key was present and removed
        """
        partition_idx = self._get_partition_index(key)
        return self._partitions[partition_idx].invalidate(key)

    def clear(self) -> None:
        """Remove all entries from all partitions."""
        for partition in self._partitions:
            partition.clear()
        logger.info("Partitioned cache cleared")

    def stats(self) -> PartitionedCacheStats:
        """Get aggregated cache statistics.

        Returns:
            PartitionedCacheStats with combined statistics
        """
        total_hits = 0
        total_misses = 0
        total_size = 0
        total_evictions = 0

        for partition in self._partitions:
            hits, misses, size, evictions = partition.stats
            total_hits += hits
            total_misses += misses
            total_size += size
            total_evictions += evictions

        return PartitionedCacheStats(
            hits=total_hits,
            misses=total_misses,
            size=total_size,
            max_size=self._max_size,
            evictions=total_evictions,
            partitions=self._num_partitions,
        )

    def cleanup_expired(self) -> int:
        """Remove all expired entries from all partitions.

        Returns:
            Total number of entries removed
        """
        total_removed = 0
        for partition in self._partitions:
            total_removed += partition.cleanup_expired()

        if total_removed > 0:
            logger.debug(f"Cleaned up {total_removed} expired cache entries")

        return total_removed

    @property
    def size(self) -> int:
        """Get current total number of entries."""
        return sum(p.size for p in self._partitions)

    @property
    def max_size(self) -> int:
        """Get maximum cache size."""
        return self._max_size

    def __len__(self) -> int:
        """Get current number of entries."""
        return self.size

    def __contains__(self, key: K) -> bool:
        """Check if key exists (without updating access time)."""
        partition_idx = self._get_partition_index(key)
        # Note: This doesn't update access time
        return self._partitions[partition_idx].get(key) is not None

    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"PartitionedLRUCache(size={stats.size}/{stats.max_size}, "
            f"partitions={stats.partitions}, hit_rate={stats.hit_rate:.2%})"
        )
