"""Redis-based distributed cache for face embeddings.

Provides a distributed caching layer for face embeddings and verification
results to reduce redundant ML inference operations and improve latency.
"""

import json
import hashlib
import logging
from typing import Optional
from datetime import datetime

import numpy as np
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisEmbeddingCache:
    """Distributed cache for face embeddings using Redis.

    Features:
    - Image hash-based caching for embedding reuse
    - TTL-based expiration for automatic cleanup
    - Async operations for non-blocking I/O
    - Efficient numpy array serialization

    Usage:
        cache = RedisEmbeddingCache()

        # Cache an embedding
        image_hash = cache.hash_image(image_bytes)
        await cache.set_embedding(image_hash, embedding_vector)

        # Retrieve cached embedding
        cached = await cache.get_embedding(image_hash)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        embedding_ttl: int = 3600,  # 1 hour for embeddings
        verification_ttl: int = 60,  # 1 minute for verification results
        prefix: str = "biometric",
    ):
        """Initialize Redis embedding cache.

        Args:
            redis_url: Redis connection URL. If None, uses settings.redis_url
            embedding_ttl: TTL for cached embeddings in seconds
            verification_ttl: TTL for verification results in seconds
            prefix: Key prefix for cache entries
        """
        self.redis_url = redis_url or settings.redis_url
        self.embedding_ttl = embedding_ttl
        self.verification_ttl = verification_ttl
        self.prefix = prefix
        self._redis: Optional[redis.Redis] = None
        self._connected = False

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection.

        Returns:
            Redis client instance

        Raises:
            ConnectionError: If Redis is unavailable
        """
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # Need bytes for numpy serialization
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
            self._connected = True
            logger.info(f"Redis embedding cache connected: {self.redis_url}")
        return self._redis

    async def is_available(self) -> bool:
        """Check if Redis is available.

        Returns:
            True if Redis connection is healthy
        """
        try:
            r = await self._get_redis()
            await r.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            return False

    @staticmethod
    def hash_image(image_data: bytes) -> str:
        """Generate SHA-256 hash of image bytes.

        Used as cache key for embedding lookups.

        Args:
            image_data: Raw image bytes

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(image_data).hexdigest()

    def _embedding_key(self, image_hash: str, model: str = "Facenet512") -> str:
        """Generate cache key for embedding.

        Args:
            image_hash: SHA-256 hash of image
            model: Model name used for extraction

        Returns:
            Redis key string
        """
        return f"{self.prefix}:embedding:{model}:{image_hash}"

    def _verification_key(self, user_id: str, image_hash: str) -> str:
        """Generate cache key for verification result.

        Args:
            user_id: User identifier
            image_hash: SHA-256 hash of probe image

        Returns:
            Redis key string
        """
        return f"{self.prefix}:verify:{user_id}:{image_hash}"

    def _user_embedding_key(self, user_id: str, tenant_id: str) -> str:
        """Generate cache key for user's enrolled embedding.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier

        Returns:
            Redis key string
        """
        return f"{self.prefix}:enrolled:{tenant_id}:{user_id}"

    @staticmethod
    def _serialize_embedding(embedding: np.ndarray) -> bytes:
        """Serialize numpy array to bytes.

        Uses JSON for portability. For production with large embeddings,
        consider using msgpack or numpy's tobytes() for better performance.

        Args:
            embedding: Numpy array to serialize

        Returns:
            Serialized bytes
        """
        return json.dumps(embedding.tolist()).encode("utf-8")

    @staticmethod
    def _deserialize_embedding(data: bytes) -> np.ndarray:
        """Deserialize bytes to numpy array.

        Args:
            data: Serialized embedding bytes

        Returns:
            Numpy array (float32)
        """
        return np.array(json.loads(data.decode("utf-8")), dtype=np.float32)

    # =========================================================================
    # Embedding Operations
    # =========================================================================

    async def get_embedding(
        self,
        image_hash: str,
        model: str = "Facenet512",
    ) -> Optional[np.ndarray]:
        """Retrieve cached embedding by image hash.

        Args:
            image_hash: SHA-256 hash of image
            model: Model name used for extraction

        Returns:
            Cached embedding array or None if not found
        """
        try:
            r = await self._get_redis()
            key = self._embedding_key(image_hash, model)

            data = await r.get(key)
            if data:
                logger.debug(f"Cache hit for embedding: {image_hash[:16]}...")
                return self._deserialize_embedding(data)

            logger.debug(f"Cache miss for embedding: {image_hash[:16]}...")
            return None

        except Exception as e:
            logger.warning(f"Redis get_embedding failed: {e}")
            return None

    async def set_embedding(
        self,
        image_hash: str,
        embedding: np.ndarray,
        model: str = "Facenet512",
        ttl: Optional[int] = None,
    ):
        """Cache embedding with TTL.

        Args:
            image_hash: SHA-256 hash of image
            embedding: Embedding vector to cache
            model: Model name used for extraction
            ttl: Custom TTL in seconds (uses default if None)
        """
        try:
            r = await self._get_redis()
            key = self._embedding_key(image_hash, model)
            ttl = ttl or self.embedding_ttl

            data = self._serialize_embedding(embedding)
            await r.setex(key, ttl, data)

            logger.debug(f"Cached embedding: {image_hash[:16]}... (TTL: {ttl}s)")

        except Exception as e:
            logger.warning(f"Redis set_embedding failed: {e}")

    # =========================================================================
    # Verification Result Operations
    # =========================================================================

    async def get_verification_result(
        self,
        user_id: str,
        image_hash: str,
    ) -> Optional[dict]:
        """Retrieve cached verification result.

        Args:
            user_id: User identifier
            image_hash: SHA-256 hash of probe image

        Returns:
            Cached verification result dict or None
        """
        try:
            r = await self._get_redis()
            key = self._verification_key(user_id, image_hash)

            data = await r.get(key)
            if data:
                logger.debug(f"Cache hit for verification: {user_id}")
                return json.loads(data.decode("utf-8"))

            return None

        except Exception as e:
            logger.warning(f"Redis get_verification_result failed: {e}")
            return None

    async def set_verification_result(
        self,
        user_id: str,
        image_hash: str,
        result: dict,
        ttl: Optional[int] = None,
    ):
        """Cache verification result with short TTL.

        Args:
            user_id: User identifier
            image_hash: SHA-256 hash of probe image
            result: Verification result dictionary
            ttl: Custom TTL in seconds (uses default if None)
        """
        try:
            r = await self._get_redis()
            key = self._verification_key(user_id, image_hash)
            ttl = ttl or self.verification_ttl

            data = json.dumps(result).encode("utf-8")
            await r.setex(key, ttl, data)

            logger.debug(f"Cached verification result: {user_id} (TTL: {ttl}s)")

        except Exception as e:
            logger.warning(f"Redis set_verification_result failed: {e}")

    # =========================================================================
    # User Enrolled Embedding Operations
    # =========================================================================

    async def get_enrolled_embedding(
        self,
        user_id: str,
        tenant_id: str,
    ) -> Optional[np.ndarray]:
        """Retrieve cached enrolled embedding for user.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier

        Returns:
            Cached embedding or None
        """
        try:
            r = await self._get_redis()
            key = self._user_embedding_key(user_id, tenant_id)

            data = await r.get(key)
            if data:
                return self._deserialize_embedding(data)
            return None

        except Exception as e:
            logger.warning(f"Redis get_enrolled_embedding failed: {e}")
            return None

    async def set_enrolled_embedding(
        self,
        user_id: str,
        tenant_id: str,
        embedding: np.ndarray,
        ttl: int = 3600,  # 1 hour default
    ):
        """Cache enrolled embedding for user.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            embedding: Enrolled embedding vector
            ttl: TTL in seconds
        """
        try:
            r = await self._get_redis()
            key = self._user_embedding_key(user_id, tenant_id)

            data = self._serialize_embedding(embedding)
            await r.setex(key, ttl, data)

        except Exception as e:
            logger.warning(f"Redis set_enrolled_embedding failed: {e}")

    # =========================================================================
    # Cache Management
    # =========================================================================

    async def invalidate_user_cache(self, user_id: str, tenant_id: Optional[str] = None):
        """Invalidate all cache entries for a user.

        Should be called when user re-enrolls or is deleted.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier
        """
        try:
            r = await self._get_redis()

            # Invalidate verification cache
            pattern = f"{self.prefix}:verify:{user_id}:*"
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break

            # Invalidate enrolled embedding cache
            if tenant_id:
                enrolled_key = self._user_embedding_key(user_id, tenant_id)
                await r.delete(enrolled_key)
                deleted += 1

            logger.info(f"Invalidated {deleted} cache entries for user {user_id}")

        except Exception as e:
            logger.warning(f"Redis invalidate_user_cache failed: {e}")

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        try:
            r = await self._get_redis()
            info = await r.info("stats")

            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses

            return {
                "hits": hits,
                "misses": misses,
                "hit_rate": round(hits / total, 4) if total > 0 else 0,
                "connected": self._connected,
                "prefix": self.prefix,
            }

        except Exception as e:
            logger.warning(f"Redis get_stats failed: {e}")
            return {
                "hits": 0,
                "misses": 0,
                "hit_rate": 0,
                "connected": False,
                "error": str(e),
            }

    async def clear_all(self, confirm: bool = False):
        """Clear all cache entries.

        WARNING: This removes all cached data. Use with caution.

        Args:
            confirm: Must be True to actually clear
        """
        if not confirm:
            logger.warning("clear_all called without confirmation, skipping")
            return

        try:
            r = await self._get_redis()
            pattern = f"{self.prefix}:*"

            cursor = 0
            deleted = 0

            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break

            logger.warning(f"Cleared {deleted} cache entries")

        except Exception as e:
            logger.error(f"Redis clear_all failed: {e}")

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._connected = False
            logger.info("Redis embedding cache connection closed")


# =============================================================================
# Global Cache Instance
# =============================================================================

_cache: Optional[RedisEmbeddingCache] = None


def get_embedding_cache() -> RedisEmbeddingCache:
    """Get global cache instance.

    Returns:
        Singleton RedisEmbeddingCache instance
    """
    global _cache
    if _cache is None:
        _cache = RedisEmbeddingCache()
    return _cache


async def close_embedding_cache():
    """Close global cache instance."""
    global _cache
    if _cache:
        await _cache.close()
        _cache = None
