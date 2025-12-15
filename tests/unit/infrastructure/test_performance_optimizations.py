"""Unit tests for performance optimization components.

Tests the following components:
- ThreadPoolManager
- ThreadSafeLRUCache
- CachedEmbeddingExtractor
- Image hashing utilities
- AsyncFaceDetector
- AsyncEmbeddingExtractor
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache, CacheStats
from app.infrastructure.caching.image_hash import (
    compute_image_hash,
    compute_embedding_cache_key,
    compute_face_region_hash,
)


# ============================================================================
# ThreadPoolManager Tests
# ============================================================================


class TestThreadPoolManager:
    """Tests for ThreadPoolManager."""

    def test_init_default_workers(self):
        """Test initialization with default worker count."""
        pool = ThreadPoolManager()
        assert pool.max_workers >= 1
        assert not pool.is_shutdown
        pool.shutdown()

    def test_init_custom_workers(self):
        """Test initialization with custom worker count."""
        pool = ThreadPoolManager(max_workers=2, thread_name_prefix="test")
        assert pool.max_workers == 2
        pool.shutdown()

    @pytest.mark.asyncio
    async def test_run_blocking_simple(self):
        """Test running a simple blocking function."""
        pool = ThreadPoolManager(max_workers=2)

        def blocking_func(x: int) -> int:
            time.sleep(0.01)  # Simulate work
            return x * 2

        result = await pool.run_blocking(blocking_func, 5)
        assert result == 10
        pool.shutdown()

    @pytest.mark.asyncio
    async def test_run_blocking_with_kwargs(self):
        """Test running blocking function with kwargs."""
        pool = ThreadPoolManager(max_workers=2)

        def blocking_func(a: int, b: int = 10) -> int:
            return a + b

        result = await pool.run_blocking(blocking_func, 5, b=15)
        assert result == 20
        pool.shutdown()

    @pytest.mark.asyncio
    async def test_run_blocking_concurrent(self):
        """Test concurrent execution of blocking functions."""
        pool = ThreadPoolManager(max_workers=4)

        def slow_func(x: int) -> int:
            time.sleep(0.05)
            return x

        # Run multiple tasks concurrently
        tasks = [pool.run_blocking(slow_func, i) for i in range(4)]
        start = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # Should complete in ~50ms (parallel) not ~200ms (sequential)
        assert elapsed < 0.15
        assert sorted(results) == [0, 1, 2, 3]
        pool.shutdown()

    @pytest.mark.asyncio
    async def test_run_blocking_after_shutdown(self):
        """Test that running after shutdown raises error."""
        pool = ThreadPoolManager(max_workers=2)
        pool.shutdown()

        with pytest.raises(RuntimeError, match="shut down"):
            await pool.run_blocking(lambda: 1)

    def test_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        pool = ThreadPoolManager(max_workers=2)
        pool.shutdown()
        pool.shutdown()  # Should not raise
        assert pool.is_shutdown


# ============================================================================
# ThreadSafeLRUCache Tests
# ============================================================================


class TestThreadSafeLRUCache:
    """Tests for ThreadSafeLRUCache."""

    def test_init_valid(self):
        """Test valid initialization."""
        cache = ThreadSafeLRUCache[str, int](max_size=100, ttl_seconds=60)
        assert cache.max_size == 100
        assert cache.size == 0

    def test_init_invalid_size(self):
        """Test initialization with invalid size."""
        with pytest.raises(ValueError, match="max_size must be"):
            ThreadSafeLRUCache[str, int](max_size=0)

    def test_put_and_get(self):
        """Test basic put and get operations."""
        cache = ThreadSafeLRUCache[str, int](max_size=10)

        cache.put("key1", 100)
        assert cache.get("key1") == 100

        cache.put("key2", 200)
        assert cache.get("key2") == 200

    def test_get_missing_key(self):
        """Test getting a non-existent key."""
        cache = ThreadSafeLRUCache[str, int](max_size=10)
        assert cache.get("missing") is None

    def test_lru_eviction(self):
        """Test LRU eviction when at capacity."""
        cache = ThreadSafeLRUCache[str, int](max_size=3)

        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)

        # Access "a" to make it recently used
        cache.get("a")

        # Add new item - should evict "b" (least recently used)
        cache.put("d", 4)

        assert cache.get("a") == 1  # Still present (was accessed)
        assert cache.get("b") is None  # Evicted
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = ThreadSafeLRUCache[str, int](max_size=10, ttl_seconds=1)

        cache.put("key", 100)
        assert cache.get("key") == 100

        # Wait for TTL to expire
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_stats(self):
        """Test cache statistics."""
        cache = ThreadSafeLRUCache[str, int](max_size=10)

        cache.put("key1", 1)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.size == 1
        assert stats.hit_rate == 0.5

    def test_invalidate(self):
        """Test invalidating a specific key."""
        cache = ThreadSafeLRUCache[str, int](max_size=10)

        cache.put("key", 100)
        assert cache.invalidate("key") is True
        assert cache.get("key") is None
        assert cache.invalidate("key") is False  # Already removed

    def test_clear(self):
        """Test clearing the cache."""
        cache = ThreadSafeLRUCache[str, int](max_size=10)

        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()

        assert cache.size == 0
        assert cache.get("a") is None

    def test_contains(self):
        """Test __contains__ check."""
        cache = ThreadSafeLRUCache[str, int](max_size=10)

        cache.put("key", 100)
        assert "key" in cache
        assert "missing" not in cache


# ============================================================================
# Image Hashing Tests
# ============================================================================


class TestImageHashing:
    """Tests for image hashing utilities."""

    def test_compute_image_hash_basic(self):
        """Test basic image hash computation."""
        # Create a simple test image
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        hash_value = compute_image_hash(image)
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_compute_image_hash_deterministic(self):
        """Test that same image produces same hash."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        hash1 = compute_image_hash(image)
        hash2 = compute_image_hash(image)
        assert hash1 == hash2

    def test_compute_image_hash_different_images(self):
        """Test that different images produce different hashes."""
        # Use patterned images instead of uniform to get different DCT hashes
        np.random.seed(42)
        image1 = np.random.randint(0, 128, (100, 100, 3), dtype=np.uint8)
        np.random.seed(123)
        image2 = np.random.randint(128, 255, (100, 100, 3), dtype=np.uint8)

        hash1 = compute_image_hash(image1)
        hash2 = compute_image_hash(image2)
        assert hash1 != hash2

    def test_compute_image_hash_grayscale(self):
        """Test hash computation for grayscale image."""
        image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)

        hash_value = compute_image_hash(image)
        assert isinstance(hash_value, str)

    def test_compute_embedding_cache_key(self):
        """Test embedding cache key generation."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        key = compute_embedding_cache_key(image, "Facenet")
        assert "Facenet" in key
        assert ":" in key

    def test_compute_embedding_cache_key_with_params(self):
        """Test cache key with extra parameters."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        key = compute_embedding_cache_key(
            image, "Facenet", extra_params={"normalize": True}
        )
        assert "normalize=True" in key

    def test_compute_face_region_hash(self):
        """Test face region hash computation."""
        image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        bbox = (50, 50, 100, 100)

        hash_value = compute_face_region_hash(image, bbox)
        assert "_50_50_100_100" in hash_value


# ============================================================================
# CachedEmbeddingExtractor Tests
# ============================================================================


class TestCachedEmbeddingExtractor:
    """Tests for CachedEmbeddingExtractor."""

    @pytest.fixture
    def mock_extractor(self):
        """Create a mock extractor."""
        extractor = MagicMock()
        extractor.get_model_name.return_value = "Facenet"
        extractor.get_embedding_dimension.return_value = 128
        extractor.extract_sync.return_value = np.random.randn(128).astype(np.float32)
        return extractor

    @pytest.fixture
    def embedding_cache(self):
        """Create an embedding cache."""
        return ThreadSafeLRUCache[str, np.ndarray](max_size=100)

    def test_sync_extraction_caches_result(self, mock_extractor, embedding_cache):
        """Test that sync extraction caches the result."""
        from app.infrastructure.caching.cached_embedding_extractor import (
            CachedEmbeddingExtractor,
        )

        cached_extractor = CachedEmbeddingExtractor(
            mock_extractor, embedding_cache, "Facenet"
        )

        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        # First call - should hit the extractor
        result1 = cached_extractor.extract_sync(image)
        assert mock_extractor.extract_sync.call_count == 1

        # Second call - should hit cache
        result2 = cached_extractor.extract_sync(image)
        assert mock_extractor.extract_sync.call_count == 1  # Still 1

        # Results should be equal
        np.testing.assert_array_equal(result1, result2)

    def test_cache_stats(self, mock_extractor, embedding_cache):
        """Test cache statistics."""
        from app.infrastructure.caching.cached_embedding_extractor import (
            CachedEmbeddingExtractor,
        )

        cached_extractor = CachedEmbeddingExtractor(
            mock_extractor, embedding_cache, "Facenet"
        )

        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        cached_extractor.extract_sync(image)  # Miss
        cached_extractor.extract_sync(image)  # Hit

        stats = cached_extractor.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_invalidate(self, mock_extractor, embedding_cache):
        """Test cache invalidation."""
        from app.infrastructure.caching.cached_embedding_extractor import (
            CachedEmbeddingExtractor,
        )

        cached_extractor = CachedEmbeddingExtractor(
            mock_extractor, embedding_cache, "Facenet"
        )

        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        cached_extractor.extract_sync(image)
        assert cached_extractor.invalidate(image) is True

        # Next call should hit extractor again
        cached_extractor.extract_sync(image)
        assert mock_extractor.extract_sync.call_count == 2


# ============================================================================
# Async Wrapper Tests
# ============================================================================


class TestAsyncWrappers:
    """Tests for async wrapper classes."""

    @pytest.fixture
    def thread_pool(self):
        """Create a thread pool for tests."""
        pool = ThreadPoolManager(max_workers=2)
        yield pool
        pool.shutdown()

    @pytest.mark.asyncio
    async def test_async_face_detector(self, thread_pool):
        """Test AsyncFaceDetector wrapper."""
        from app.infrastructure.async_execution.async_face_detector import (
            AsyncFaceDetector,
        )
        from app.domain.entities.face_detection import FaceDetectionResult

        # Create mock detector
        mock_detector = MagicMock()
        mock_detector.get_detector_name.return_value = "opencv"
        mock_detector.detect_sync.return_value = FaceDetectionResult(
            found=True,
            bounding_box=(10, 10, 100, 100),
            landmarks=None,
            confidence=0.99,
        )

        async_detector = AsyncFaceDetector(mock_detector, thread_pool)
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        result = await async_detector.detect(image)
        assert result.found is True
        assert result.confidence == 0.99
        mock_detector.detect_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_embedding_extractor(self, thread_pool):
        """Test AsyncEmbeddingExtractor wrapper."""
        from app.infrastructure.async_execution.async_embedding_extractor import (
            AsyncEmbeddingExtractor,
        )

        # Create mock extractor
        mock_extractor = MagicMock()
        mock_extractor.get_model_name.return_value = "Facenet"
        mock_extractor.get_embedding_dimension.return_value = 128
        expected_embedding = np.random.randn(128).astype(np.float32)
        mock_extractor.extract_sync.return_value = expected_embedding

        async_extractor = AsyncEmbeddingExtractor(mock_extractor, thread_pool)
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        result = await async_extractor.extract(image)
        np.testing.assert_array_equal(result, expected_embedding)
        mock_extractor.extract_sync.assert_called_once()


# ============================================================================
# ThreadSafe Repository Tests
# ============================================================================


class TestThreadSafeInMemoryRepository:
    """Tests for ThreadSafeInMemoryEmbeddingRepository."""

    @pytest.fixture
    def repository(self):
        """Create a repository instance."""
        from app.infrastructure.persistence.repositories.thread_safe_memory_repository import (
            ThreadSafeInMemoryEmbeddingRepository,
        )
        return ThreadSafeInMemoryEmbeddingRepository(max_capacity=100)

    @pytest.mark.asyncio
    async def test_save_and_find(self, repository):
        """Test basic save and find operations."""
        embedding = np.random.randn(128).astype(np.float32)

        await repository.save("user1", embedding, quality_score=85.0)

        result = await repository.find_by_user_id("user1")
        assert result is not None
        # Embeddings are normalized on save
        norm = np.linalg.norm(embedding)
        expected = embedding / norm
        np.testing.assert_array_almost_equal(result, expected, decimal=5)

    @pytest.mark.asyncio
    async def test_find_similar_vectorized(self, repository):
        """Test vectorized similarity search."""
        # Create some test embeddings
        for i in range(10):
            embedding = np.random.randn(128).astype(np.float32)
            await repository.save(f"user{i}", embedding, quality_score=80.0)

        # Search with a random query
        query = np.random.randn(128).astype(np.float32)
        results = await repository.find_similar(query, threshold=2.0, limit=5)

        assert len(results) <= 5
        # Results should be sorted by distance
        if len(results) > 1:
            distances = [r[1] for r in results]
            assert distances == sorted(distances)

    @pytest.mark.asyncio
    async def test_lru_eviction(self, repository):
        """Test LRU eviction at capacity."""
        # Fill beyond capacity
        for i in range(110):
            embedding = np.random.randn(128).astype(np.float32)
            await repository.save(f"user{i}", embedding, quality_score=80.0)

        # Should have evicted some entries
        count = await repository.count()
        assert count == 100  # max_capacity

    @pytest.mark.asyncio
    async def test_delete(self, repository):
        """Test deletion."""
        embedding = np.random.randn(128).astype(np.float32)
        await repository.save("user1", embedding, quality_score=85.0)

        assert await repository.delete("user1") is True
        assert await repository.exists("user1") is False
        assert await repository.delete("user1") is False


# ============================================================================
# AutoCleaningMemoryStorage Tests
# ============================================================================


class TestAutoCleaningMemoryStorage:
    """Tests for AutoCleaningMemoryStorage."""

    @pytest.fixture
    def storage(self):
        """Create a storage instance."""
        from app.infrastructure.rate_limit.auto_cleaning_memory_storage import (
            AutoCleaningMemoryStorage,
        )
        return AutoCleaningMemoryStorage(max_entries=100, cleanup_interval_seconds=60)

    @pytest.mark.asyncio
    async def test_increment(self, storage):
        """Test rate limit increment."""
        info = await storage.increment("user1", limit=60, window_seconds=60)

        assert info.limit == 60
        assert info.remaining == 59

    @pytest.mark.asyncio
    async def test_increment_exceeds_limit(self, storage):
        """Test incrementing beyond limit."""
        for _ in range(60):
            await storage.increment("user1", limit=60, window_seconds=60)

        info = await storage.increment("user1", limit=60, window_seconds=60)
        assert info.remaining == 0

    @pytest.mark.asyncio
    async def test_lru_eviction(self, storage):
        """Test LRU eviction at capacity."""
        # Fill beyond capacity
        for i in range(110):
            await storage.increment(f"user{i}", limit=60, window_seconds=60)

        stats = storage.get_stats()
        assert stats["size"] == 100  # max_entries

    @pytest.mark.asyncio
    async def test_reset(self, storage):
        """Test reset functionality."""
        await storage.increment("user1", limit=60, window_seconds=60)
        await storage.reset("user1")

        info = await storage.get("user1")
        assert info is not None
        # After reset in same window, remaining should be at limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
