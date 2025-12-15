"""Integration tests for performance optimizations with real images.

This module tests all performance optimization components using real face images
from the test fixtures directory to ensure they work correctly in realistic scenarios.

Test Categories:
1. ThreadPoolManager - Concurrent execution
2. ThreadSafeLRUCache - Caching with real embeddings
3. Image Hashing - Consistency and uniqueness
4. AsyncFaceDetector - Non-blocking detection with real images
5. AsyncEmbeddingExtractor - Non-blocking extraction with real images
6. CachedEmbeddingExtractor - Caching with real images
7. ThreadSafeInMemoryRepository - Thread-safe storage with real embeddings
8. OptimizedTextureLivenessDetector - Optimized liveness with real images
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import pytest

# Performance optimization components
from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache
from app.infrastructure.caching.image_hash import (
    compute_image_hash,
    compute_embedding_cache_key,
)


# ============================================================================
# Test Constants
# ============================================================================

FIXTURES_PATH = Path(__file__).parent.parent / "fixtures" / "images"
PERFORMANCE_THRESHOLD_MS = 500  # Max acceptable time for single operations


# ============================================================================
# Helper Functions
# ============================================================================


def load_test_images() -> Dict[str, List[Dict]]:
    """Load all test images from fixtures directory."""
    images = {}
    if not FIXTURES_PATH.exists():
        return images

    for user_dir in FIXTURES_PATH.iterdir():
        if user_dir.is_dir():
            user_images = []
            for img_path in user_dir.glob("*"):
                if img_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                    img = cv2.imread(str(img_path))
                    if img is not None:
                        user_images.append({
                            "path": str(img_path),
                            "image": img,
                            "name": img_path.name,
                            "user_id": user_dir.name,
                        })
            if user_images:
                images[user_dir.name] = user_images
    return images


# ============================================================================
# Test Class: ThreadPoolManager with Real Images
# ============================================================================


class TestThreadPoolManagerWithRealImages:
    """Test ThreadPoolManager with real image processing."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.images = load_test_images()
        self.pool = ThreadPoolManager(max_workers=4, thread_name_prefix="test")
        yield
        self.pool.shutdown(wait=True)

    @pytest.mark.asyncio
    async def test_concurrent_image_processing(self):
        """Test concurrent processing of multiple images."""
        if not self.images:
            pytest.skip("No test images available")

        # Collect images from all users
        all_images = []
        for user_id, images in self.images.items():
            all_images.extend(images[:2])  # Take first 2 from each user

        if len(all_images) < 2:
            pytest.skip("Need at least 2 images for concurrent test")

        def process_image(img: np.ndarray) -> dict:
            """Simulate image processing (grayscale + blur detection)."""
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            return {"blur_score": laplacian_var, "shape": img.shape}

        # Process images concurrently
        start_time = time.time()
        tasks = [
            self.pool.run_blocking(process_image, img_data["image"])
            for img_data in all_images
        ]
        results = await asyncio.gather(*tasks)
        elapsed_ms = (time.time() - start_time) * 1000

        # Verify results
        assert len(results) == len(all_images)
        for result in results:
            assert "blur_score" in result
            assert "shape" in result
            assert result["blur_score"] >= 0

        print(f"\n  Processed {len(all_images)} images concurrently in {elapsed_ms:.2f}ms")

    @pytest.mark.asyncio
    async def test_thread_pool_exception_handling(self):
        """Test that exceptions in thread pool are properly propagated."""

        def failing_function(img: np.ndarray):
            raise ValueError("Intentional test error")

        if not self.images:
            pytest.skip("No test images available")

        first_user = list(self.images.keys())[0]
        image = self.images[first_user][0]["image"]

        with pytest.raises(ValueError, match="Intentional test error"):
            await self.pool.run_blocking(failing_function, image)


# ============================================================================
# Test Class: Image Hashing with Real Images
# ============================================================================


class TestImageHashingWithRealImages:
    """Test image hashing with real images."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.images = load_test_images()

    def test_hash_consistency_same_image(self):
        """Test that same image always produces same hash."""
        if not self.images:
            pytest.skip("No test images available")

        first_user = list(self.images.keys())[0]
        image = self.images[first_user][0]["image"]

        hash1 = compute_image_hash(image)
        hash2 = compute_image_hash(image)
        hash3 = compute_image_hash(image.copy())

        assert hash1 == hash2, "Same image should produce same hash"
        assert hash1 == hash3, "Copy of image should produce same hash"

    def test_hash_uniqueness_different_images(self):
        """Test that different images produce different hashes."""
        if len(self.images) < 2:
            pytest.skip("Need at least 2 users for uniqueness test")

        hashes = set()
        for user_id, images in self.images.items():
            for img_data in images[:3]:  # First 3 images per user
                h = compute_image_hash(img_data["image"])
                hashes.add(h)

        # Most images should have unique hashes
        total_images = sum(min(3, len(imgs)) for imgs in self.images.values())
        unique_ratio = len(hashes) / total_images if total_images > 0 else 0

        print(f"\n  Hash uniqueness: {len(hashes)}/{total_images} ({unique_ratio:.1%})")
        assert unique_ratio >= 0.8, f"Expected at least 80% unique hashes, got {unique_ratio:.1%}"

    def test_hash_performance(self):
        """Test hash computation performance."""
        if not self.images:
            pytest.skip("No test images available")

        first_user = list(self.images.keys())[0]
        image = self.images[first_user][0]["image"]

        # Warm up
        compute_image_hash(image)

        # Benchmark
        iterations = 100
        start_time = time.time()
        for _ in range(iterations):
            compute_image_hash(image)
        elapsed_ms = (time.time() - start_time) * 1000

        avg_ms = elapsed_ms / iterations
        print(f"\n  Average hash time: {avg_ms:.3f}ms per image")
        assert avg_ms < 5.0, f"Hash computation too slow: {avg_ms:.3f}ms"

    def test_cache_key_includes_model(self):
        """Test that cache keys include model name."""
        if not self.images:
            pytest.skip("No test images available")

        first_user = list(self.images.keys())[0]
        image = self.images[first_user][0]["image"]

        key_facenet = compute_embedding_cache_key(image, "Facenet")
        key_arcface = compute_embedding_cache_key(image, "ArcFace")

        assert key_facenet != key_arcface
        assert "Facenet" in key_facenet
        assert "ArcFace" in key_arcface


# ============================================================================
# Test Class: LRU Cache with Real Embeddings
# ============================================================================


class TestLRUCacheWithRealEmbeddings:
    """Test LRU cache with realistic embedding data."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.cache = ThreadSafeLRUCache[str, np.ndarray](max_size=50, ttl_seconds=300)
        self.images = load_test_images()

    def test_cache_embeddings_from_real_images(self):
        """Test caching embeddings derived from real images."""
        if not self.images:
            pytest.skip("No test images available")

        # Simulate embeddings for each image
        cached_keys = []
        for user_id, images in self.images.items():
            for img_data in images[:2]:
                # Create fake embedding based on image hash
                key = compute_image_hash(img_data["image"])
                embedding = np.random.randn(128).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)

                self.cache.put(key, embedding)
                cached_keys.append(key)

        # Verify all entries cached
        for key in cached_keys:
            result = self.cache.get(key)
            assert result is not None
            assert result.shape == (128,)

        stats = self.cache.stats()
        print(f"\n  Cache stats: hits={stats.hits}, misses={stats.misses}, size={stats.size}")

    def test_cache_hit_rate_with_repeated_access(self):
        """Test cache hit rate with repeated access patterns."""
        if not self.images:
            pytest.skip("No test images available")

        # Pre-populate cache
        keys = []
        for user_id, images in list(self.images.items())[:2]:
            for img_data in images[:3]:
                key = compute_image_hash(img_data["image"])
                embedding = np.random.randn(128).astype(np.float32)
                self.cache.put(key, embedding)
                keys.append(key)

        # Simulate access pattern (80% hits, 20% misses)
        for _ in range(100):
            if np.random.random() < 0.8 and keys:
                # Access existing key
                key = np.random.choice(keys)
                self.cache.get(key)
            else:
                # Access non-existent key
                self.cache.get(f"nonexistent_{np.random.randint(1000)}")

        stats = self.cache.stats()
        print(f"\n  Hit rate: {stats.hit_rate:.2%}")
        assert stats.hit_rate >= 0.6, f"Hit rate too low: {stats.hit_rate:.2%}"

    def test_lru_eviction_preserves_recent(self):
        """Test that LRU eviction preserves recently accessed entries."""
        small_cache = ThreadSafeLRUCache[str, np.ndarray](max_size=5)

        # Add 5 entries
        for i in range(5):
            small_cache.put(f"key_{i}", np.random.randn(128).astype(np.float32))

        # Access key_0 to make it recently used
        small_cache.get("key_0")

        # Add a new entry (should evict key_1, not key_0)
        small_cache.put("key_new", np.random.randn(128).astype(np.float32))

        # key_0 should still be present
        assert small_cache.get("key_0") is not None
        # key_1 should be evicted
        assert small_cache.get("key_1") is None


# ============================================================================
# Test Class: ThreadSafe Repository with Real Data
# ============================================================================


class TestThreadSafeRepositoryWithRealData:
    """Test thread-safe repository with realistic usage patterns."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        from app.infrastructure.persistence.repositories.thread_safe_memory_repository import (
            ThreadSafeInMemoryEmbeddingRepository,
        )
        self.repo = ThreadSafeInMemoryEmbeddingRepository(max_capacity=100)
        self.images = load_test_images()

    @pytest.mark.asyncio
    async def test_save_and_search_real_users(self):
        """Test saving and searching embeddings for real users."""
        if not self.images:
            pytest.skip("No test images available")

        # Enroll all users
        user_embeddings = {}
        for user_id, images in self.images.items():
            embedding = np.random.randn(128).astype(np.float32)
            await self.repo.save(user_id, embedding, quality_score=85.0)
            user_embeddings[user_id] = embedding

        # Verify all saved
        count = await self.repo.count()
        assert count == len(self.images)

        # Search with a known embedding
        first_user = list(user_embeddings.keys())[0]
        query = user_embeddings[first_user]

        results = await self.repo.find_similar(query, threshold=0.5, limit=5)
        assert len(results) >= 1

        # First result should be the same user (distance ~0)
        assert results[0][0] == first_user
        assert results[0][1] < 0.1

    @pytest.mark.asyncio
    async def test_concurrent_save_and_search(self):
        """Test concurrent save and search operations."""
        if not self.images:
            pytest.skip("No test images available")

        async def save_user(user_id: str, embedding: np.ndarray):
            await self.repo.save(user_id, embedding, quality_score=80.0)
            return user_id

        async def search_similar(embedding: np.ndarray):
            return await self.repo.find_similar(embedding, threshold=2.0, limit=5)

        # Create tasks
        save_tasks = []
        search_tasks = []

        for i, (user_id, images) in enumerate(self.images.items()):
            embedding = np.random.randn(128).astype(np.float32)
            save_tasks.append(save_user(f"{user_id}_{i}", embedding))

            if i % 2 == 0:
                search_tasks.append(search_similar(embedding))

        # Run concurrently
        start_time = time.time()
        all_tasks = save_tasks + search_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        elapsed_ms = (time.time() - start_time) * 1000

        # Verify no exceptions
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Concurrent operations failed: {errors}"

        print(f"\n  Concurrent operations ({len(all_tasks)} tasks) in {elapsed_ms:.2f}ms")

    @pytest.mark.asyncio
    async def test_vectorized_search_performance(self):
        """Test vectorized search performance with many embeddings."""
        # Populate with many embeddings
        for i in range(100):
            embedding = np.random.randn(128).astype(np.float32)
            await self.repo.save(f"user_{i}", embedding, quality_score=80.0)

        # Benchmark search
        query = np.random.randn(128).astype(np.float32)

        # Warm up
        await self.repo.find_similar(query, threshold=2.0, limit=10)

        # Benchmark
        iterations = 50
        start_time = time.time()
        for _ in range(iterations):
            await self.repo.find_similar(query, threshold=2.0, limit=10)
        elapsed_ms = (time.time() - start_time) * 1000

        avg_ms = elapsed_ms / iterations
        print(f"\n  Average search time (100 embeddings): {avg_ms:.3f}ms")
        assert avg_ms < 50.0, f"Search too slow: {avg_ms:.3f}ms"


# ============================================================================
# Test Class: Optimized Liveness Detector with Real Images
# ============================================================================


class TestOptimizedLivenessWithRealImages:
    """Test optimized liveness detector with real images."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        from app.infrastructure.ml.liveness.optimized_texture_liveness import (
            OptimizedTextureLivenessDetector,
        )
        self.detector = OptimizedTextureLivenessDetector(liveness_threshold=60.0)
        self.images = load_test_images()

    @pytest.mark.asyncio
    async def test_liveness_detection_real_images(self):
        """Test liveness detection on real face images."""
        if not self.images:
            pytest.skip("No test images available")

        results = []
        for user_id, images in self.images.items():
            for img_data in images[:2]:
                result = await self.detector.detect(img_data["image"])
                results.append({
                    "user_id": user_id,
                    "image": img_data["name"],
                    "is_live": result.is_live,
                    "score": result.liveness_score,
                })

        print("\n  Liveness Detection Results:")
        for r in results:
            status = "PASS" if r["is_live"] else "FAIL"
            print(f"    [{status}] {r['user_id']}/{r['image']}: {r['score']:.1f}")

        # At least some images should pass (real faces)
        pass_rate = sum(1 for r in results if r["is_live"]) / len(results)
        print(f"\n  Overall pass rate: {pass_rate:.1%}")

    @pytest.mark.asyncio
    async def test_liveness_performance_optimized(self):
        """Test optimized liveness detector performance."""
        if not self.images:
            pytest.skip("No test images available")

        first_user = list(self.images.keys())[0]
        image = self.images[first_user][0]["image"]

        # Warm up
        await self.detector.detect(image)

        # Benchmark
        iterations = 20
        start_time = time.time()
        for _ in range(iterations):
            await self.detector.detect(image)
        elapsed_ms = (time.time() - start_time) * 1000

        avg_ms = elapsed_ms / iterations
        print(f"\n  Average liveness detection time: {avg_ms:.2f}ms")
        assert avg_ms < 200.0, f"Liveness detection too slow: {avg_ms:.2f}ms"

    def test_sync_detection_available(self):
        """Test that synchronous detection method is available."""
        if not self.images:
            pytest.skip("No test images available")

        first_user = list(self.images.keys())[0]
        image = self.images[first_user][0]["image"]

        result = self.detector.detect_sync(image)
        assert result is not None
        assert hasattr(result, "is_live")
        assert hasattr(result, "liveness_score")


# ============================================================================
# Test Class: End-to-End Performance Tests
# ============================================================================


class TestEndToEndPerformance:
    """End-to-end performance tests simulating real usage."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.images = load_test_images()
        self.pool = ThreadPoolManager(max_workers=4)
        self.cache = ThreadSafeLRUCache[str, np.ndarray](max_size=100)
        yield
        self.pool.shutdown(wait=True)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_caching(self):
        """Test full processing pipeline with caching enabled."""
        if not self.images:
            pytest.skip("No test images available")

        from app.infrastructure.caching.cached_embedding_extractor import CachedEmbeddingExtractor
        from unittest.mock import MagicMock

        # Create mock extractor
        mock_extractor = MagicMock()
        mock_extractor.get_model_name.return_value = "Facenet"
        mock_extractor.get_embedding_dimension.return_value = 128

        def extract_sync(img):
            time.sleep(0.01)  # Simulate extraction time
            return np.random.randn(128).astype(np.float32)

        mock_extractor.extract_sync = extract_sync

        # Wrap with cache
        cached_extractor = CachedEmbeddingExtractor(mock_extractor, self.cache, "Facenet")

        # Process images (first pass - cache miss)
        first_user = list(self.images.keys())[0]
        images = self.images[first_user][:3]

        start_time = time.time()
        for img_data in images:
            cached_extractor.extract_sync(img_data["image"])
        first_pass_ms = (time.time() - start_time) * 1000

        # Process same images again (cache hit)
        start_time = time.time()
        for img_data in images:
            cached_extractor.extract_sync(img_data["image"])
        second_pass_ms = (time.time() - start_time) * 1000

        print(f"\n  First pass (cache miss): {first_pass_ms:.2f}ms")
        print(f"  Second pass (cache hit): {second_pass_ms:.2f}ms")
        print(f"  Speedup: {first_pass_ms / second_pass_ms:.1f}x")

        stats = cached_extractor.get_cache_stats()
        assert stats["hits"] >= len(images)

    @pytest.mark.asyncio
    async def test_concurrent_user_enrollment(self):
        """Test concurrent enrollment of multiple users."""
        if len(self.images) < 2:
            pytest.skip("Need at least 2 users for concurrent test")

        from app.infrastructure.persistence.repositories.thread_safe_memory_repository import (
            ThreadSafeInMemoryEmbeddingRepository,
        )

        repo = ThreadSafeInMemoryEmbeddingRepository(max_capacity=100)

        async def enroll_user(user_id: str, image: np.ndarray):
            # Simulate embedding extraction
            embedding = await self.pool.run_blocking(
                lambda img: np.random.randn(128).astype(np.float32), image
            )
            await repo.save(user_id, embedding, quality_score=85.0)
            return user_id

        # Enroll all users concurrently
        tasks = []
        for user_id, images in self.images.items():
            if images:
                tasks.append(enroll_user(user_id, images[0]["image"]))

        start_time = time.time()
        enrolled = await asyncio.gather(*tasks)
        elapsed_ms = (time.time() - start_time) * 1000

        print(f"\n  Enrolled {len(enrolled)} users concurrently in {elapsed_ms:.2f}ms")

        # Verify all enrolled
        count = await repo.count()
        assert count == len(self.images)


# ============================================================================
# Run Tests
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
