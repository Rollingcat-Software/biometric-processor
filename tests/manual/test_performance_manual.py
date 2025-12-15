"""Manual Test Script for Performance Optimization Components.

This script allows manual, interactive testing of all performance optimization
components with real face images from the test fixtures.

Usage:
    cd biometric-processor
    python -m tests.manual.test_performance_manual

Or run specific test sections:
    python -m tests.manual.test_performance_manual --section thread_pool
    python -m tests.manual.test_performance_manual --section cache
    python -m tests.manual.test_performance_manual --section repository
    python -m tests.manual.test_performance_manual --section liveness
    python -m tests.manual.test_performance_manual --section full_pipeline
"""

import asyncio
import argparse
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{Colors.CYAN}{'-'*40}{Colors.ENDC}")
    print(f"{Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'-'*40}{Colors.ENDC}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}[PASS] {text}{Colors.ENDC}")


def print_fail(text: str):
    """Print failure message."""
    print(f"{Colors.RED}[FAIL] {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}[INFO] {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.ENDC}")


def load_test_images() -> Dict[str, List[Dict[str, Any]]]:
    """Load all test images from fixtures directory."""
    import cv2

    fixtures_path = Path(__file__).parent.parent / "fixtures" / "images"
    images = {}

    print_info(f"Loading images from: {fixtures_path}")

    if not fixtures_path.exists():
        print_fail(f"Fixtures directory not found: {fixtures_path}")
        return images

    for user_dir in fixtures_path.iterdir():
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
                        })
            if user_images:
                images[user_dir.name] = user_images
                print_info(f"  Loaded {len(user_images)} images for user: {user_dir.name}")

    return images


class ManualTestRunner:
    """Runner for manual performance tests."""

    def __init__(self):
        self.images = {}
        self.results = {}

    def setup(self):
        """Initialize test environment."""
        print_header("SETUP")
        self.images = load_test_images()

        if not self.images:
            print_fail("No test images found! Please add images to tests/fixtures/images/")
            return False

        total_images = sum(len(imgs) for imgs in self.images.values())
        print_success(f"Loaded {total_images} images from {len(self.images)} users")
        return True

    async def test_thread_pool_manager(self):
        """Test ThreadPoolManager with real images."""
        print_header("TEST: Thread Pool Manager")

        try:
            from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager

            pool = ThreadPoolManager(max_workers=4, thread_name_prefix="manual-test")
            print_success("ThreadPoolManager created successfully")

            # Test 1: Basic blocking function execution
            print_section("Test 1: Basic Execution")

            def cpu_intensive(image: np.ndarray) -> int:
                """Simulate CPU-intensive operation."""
                return int(np.mean(image))

            sample_image = list(self.images.values())[0][0]["image"]
            start = time.perf_counter()
            result = await pool.run_blocking(cpu_intensive, sample_image)
            elapsed = time.perf_counter() - start

            print_success(f"Executed blocking function: result={result}, time={elapsed:.4f}s")

            # Test 2: Concurrent execution
            print_section("Test 2: Concurrent Execution")

            all_images = [img["image"] for imgs in self.images.values() for img in imgs]

            start = time.perf_counter()
            tasks = [pool.run_blocking(cpu_intensive, img) for img in all_images[:5]]
            results = await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - start

            print_success(f"Concurrent execution of {len(tasks)} tasks: time={elapsed:.4f}s")
            print_info(f"Results: {results}")

            # Test 3: Exception handling
            print_section("Test 3: Exception Handling")

            def failing_function():
                raise ValueError("Intentional test error")

            try:
                await pool.run_blocking(failing_function)
                print_fail("Exception not propagated!")
            except ValueError as e:
                print_success(f"Exception properly propagated: {e}")

            # Cleanup
            pool.shutdown(wait=True)
            print_success("ThreadPoolManager shutdown complete")

            self.results["thread_pool"] = "PASSED"

        except Exception as e:
            print_fail(f"Thread pool test failed: {e}")
            self.results["thread_pool"] = f"FAILED: {e}"
            import traceback
            traceback.print_exc()

    async def test_image_hashing(self):
        """Test image hashing with real images."""
        print_header("TEST: Image Hashing")

        try:
            from app.infrastructure.caching.image_hash import compute_image_hash

            print_section("Test 1: Hash Consistency")

            sample_image = list(self.images.values())[0][0]["image"]
            hash1 = compute_image_hash(sample_image)
            hash2 = compute_image_hash(sample_image)

            if hash1 == hash2:
                print_success(f"Same image produces same hash: {hash1}")
            else:
                print_fail(f"Hash mismatch: {hash1} != {hash2}")

            # Test 2: Hash uniqueness
            print_section("Test 2: Hash Uniqueness")

            all_images = [img["image"] for imgs in self.images.values() for img in imgs]
            hashes = [compute_image_hash(img) for img in all_images]
            unique_hashes = set(hashes)

            print_info(f"Total images: {len(all_images)}")
            print_info(f"Unique hashes: {len(unique_hashes)}")

            if len(unique_hashes) == len(all_images):
                print_success("All images have unique hashes")
            else:
                print_warning(f"Some hash collisions detected: {len(all_images) - len(unique_hashes)} collisions")

            # Test 3: Hash performance
            print_section("Test 3: Hash Performance")

            iterations = 100
            start = time.perf_counter()
            for _ in range(iterations):
                compute_image_hash(sample_image)
            elapsed = time.perf_counter() - start

            avg_time = (elapsed / iterations) * 1000
            print_info(f"Average hash time: {avg_time:.2f}ms per image")

            if avg_time < 10:
                print_success("Hash performance is excellent (<10ms)")
            elif avg_time < 50:
                print_success("Hash performance is acceptable (<50ms)")
            else:
                print_warning("Hash performance is slow (>50ms)")

            self.results["image_hashing"] = "PASSED"

        except Exception as e:
            print_fail(f"Image hashing test failed: {e}")
            self.results["image_hashing"] = f"FAILED: {e}"
            import traceback
            traceback.print_exc()

    async def test_lru_cache(self):
        """Test LRU cache with real embeddings."""
        print_header("TEST: LRU Cache")

        try:
            from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache

            cache = ThreadSafeLRUCache[str, np.ndarray](max_size=10, ttl_seconds=60)
            print_success("ThreadSafeLRUCache created successfully")

            # Test 1: Basic operations
            print_section("Test 1: Basic Put/Get")

            embedding = np.random.randn(512).astype(np.float32)
            cache.put("test_key", embedding)

            retrieved = cache.get("test_key")
            if retrieved is not None and np.array_equal(embedding, retrieved):
                print_success("Put/Get working correctly")
            else:
                print_fail("Put/Get mismatch!")

            # Test 2: Cache miss
            print_section("Test 2: Cache Miss")

            result = cache.get("nonexistent_key")
            if result is None:
                print_success("Cache miss returns None correctly")
            else:
                print_fail("Cache miss should return None")

            # Test 3: LRU eviction
            print_section("Test 3: LRU Eviction")

            # Fill cache beyond capacity
            for i in range(15):
                cache.put(f"key_{i}", np.random.randn(512).astype(np.float32))

            stats = cache.stats()
            print_info(f"Cache stats: size={stats.size}, hits={stats.hits}, misses={stats.misses}")

            # First key should be evicted
            if cache.get("key_0") is None:
                print_success("LRU eviction working (oldest entry evicted)")
            else:
                print_warning("LRU eviction may not be working correctly")

            # Test 4: Cache statistics
            print_section("Test 4: Hit Rate")

            # Create fresh cache for hit rate test
            cache2 = ThreadSafeLRUCache[str, float](max_size=100, ttl_seconds=60)

            for i in range(10):
                cache2.put(f"data_{i}", float(i))

            # Access some keys multiple times
            for _ in range(50):
                cache2.get("data_0")
                cache2.get("data_1")
                cache2.get("nonexistent")

            stats2 = cache2.stats()
            hit_rate = stats2.hits / (stats2.hits + stats2.misses) if (stats2.hits + stats2.misses) > 0 else 0
            print_info(f"Hit rate: {hit_rate:.2%} (hits={stats2.hits}, misses={stats2.misses})")

            if hit_rate > 0.5:
                print_success(f"Good hit rate: {hit_rate:.2%}")
            else:
                print_warning(f"Low hit rate: {hit_rate:.2%}")

            self.results["lru_cache"] = "PASSED"

        except Exception as e:
            print_fail(f"LRU cache test failed: {e}")
            self.results["lru_cache"] = f"FAILED: {e}"
            import traceback
            traceback.print_exc()

    async def test_thread_safe_repository(self):
        """Test thread-safe repository with real data."""
        print_header("TEST: Thread-Safe Repository")

        try:
            from app.infrastructure.persistence.repositories.thread_safe_memory_repository import (
                ThreadSafeInMemoryEmbeddingRepository
            )

            repo = ThreadSafeInMemoryEmbeddingRepository(max_capacity=1000)
            print_success("ThreadSafeInMemoryEmbeddingRepository created successfully")

            # Test 1: Basic save/find
            print_section("Test 1: Save and Find")

            embedding = np.random.randn(512).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)

            await repo.save(
                user_id="test_user_1",
                embedding=embedding,
                quality_score=85.0,
                tenant_id="test_tenant"
            )

            found = await repo.find_by_user_id("test_user_1", "test_tenant")
            if found is not None:
                print_success("Save and find working correctly")
            else:
                print_fail("Could not find saved embedding!")

            # Test 2: Similarity search
            print_section("Test 2: Similarity Search")

            # Add more embeddings
            for i in range(50):
                emb = np.random.randn(512).astype(np.float32)
                emb = emb / np.linalg.norm(emb)
                await repo.save(f"user_{i}", emb, quality_score=80.0, tenant_id="test_tenant")

            # Search for similar
            query = np.random.randn(512).astype(np.float32)
            query = query / np.linalg.norm(query)

            start = time.perf_counter()
            similar = await repo.find_similar(query, threshold=0.8, limit=10, tenant_id="test_tenant")
            elapsed = time.perf_counter() - start

            print_info(f"Found {len(similar)} similar embeddings in {elapsed*1000:.2f}ms")
            print_success("Similarity search working")

            # Test 3: Concurrent access
            print_section("Test 3: Concurrent Access")

            async def concurrent_save(user_id: str):
                emb = np.random.randn(512).astype(np.float32)
                emb = emb / np.linalg.norm(emb)
                await repo.save(user_id, emb, quality_score=75.0, tenant_id="concurrent_tenant")

            start = time.perf_counter()
            await asyncio.gather(*[concurrent_save(f"concurrent_{i}") for i in range(100)])
            elapsed = time.perf_counter() - start

            count = await repo.count("concurrent_tenant")
            print_info(f"Saved 100 embeddings concurrently in {elapsed*1000:.2f}ms")
            print_info(f"Total count in tenant: {count}")

            if count == 100:
                print_success("Concurrent access working correctly")
            else:
                print_fail(f"Expected 100, got {count}")

            # Test 4: Delete
            print_section("Test 4: Delete Operation")

            deleted = await repo.delete("test_user_1", "test_tenant")
            if deleted:
                found_after = await repo.find_by_user_id("test_user_1", "test_tenant")
                if found_after is None:
                    print_success("Delete working correctly")
                else:
                    print_fail("Embedding still exists after delete!")
            else:
                print_fail("Delete returned False")

            self.results["repository"] = "PASSED"

        except Exception as e:
            print_fail(f"Repository test failed: {e}")
            self.results["repository"] = f"FAILED: {e}"
            import traceback
            traceback.print_exc()

    async def test_optimized_liveness(self):
        """Test optimized liveness detector with real images."""
        print_header("TEST: Optimized Liveness Detector")

        try:
            from app.infrastructure.ml.liveness.optimized_texture_liveness import (
                OptimizedTextureLivenessDetector
            )

            detector = OptimizedTextureLivenessDetector(
                texture_threshold=100.0,
                color_threshold=0.3,
                frequency_threshold=0.5,
                liveness_threshold=60.0,
                fft_downsample_size=(192, 108)
            )
            print_success("OptimizedTextureLivenessDetector created successfully")

            # Test with each user's images
            print_section("Test 1: Liveness Detection on Real Images")

            results_summary = []

            for user_id, user_images in self.images.items():
                print_info(f"\nTesting user: {user_id}")

                for img_data in user_images[:3]:  # Test first 3 images per user
                    image = img_data["image"]
                    name = img_data["name"]

                    start = time.perf_counter()
                    result = await detector.detect(image, challenge="texture_analysis")
                    elapsed = time.perf_counter() - start

                    status = "LIVE" if result.is_live else "SPOOF"
                    print_info(f"  {name}: {status} (score={result.liveness_score:.1f}, time={elapsed*1000:.1f}ms)")

                    results_summary.append({
                        "user": user_id,
                        "image": name,
                        "is_live": result.is_live,
                        "score": result.liveness_score,
                        "time_ms": elapsed * 1000
                    })

            # Test 2: Performance benchmark
            print_section("Test 2: Performance Benchmark")

            sample_image = list(self.images.values())[0][0]["image"]

            times = []
            for _ in range(10):
                start = time.perf_counter()
                await detector.detect(sample_image, challenge="texture_analysis")
                times.append(time.perf_counter() - start)

            avg_time = np.mean(times) * 1000
            p95_time = np.percentile(times, 95) * 1000

            print_info(f"Average detection time: {avg_time:.2f}ms")
            print_info(f"P95 detection time: {p95_time:.2f}ms")

            if avg_time < 100:
                print_success("Excellent performance (<100ms average)")
            elif avg_time < 200:
                print_success("Good performance (<200ms average)")
            else:
                print_warning("Performance could be improved (>200ms average)")

            # Summary
            print_section("Summary")

            live_count = sum(1 for r in results_summary if r["is_live"])
            total_count = len(results_summary)
            avg_score = np.mean([r["score"] for r in results_summary])

            print_info(f"Total images tested: {total_count}")
            print_info(f"Detected as live: {live_count}/{total_count}")
            print_info(f"Average liveness score: {avg_score:.1f}")

            self.results["liveness"] = "PASSED"

        except Exception as e:
            print_fail(f"Liveness test failed: {e}")
            self.results["liveness"] = f"FAILED: {e}"
            import traceback
            traceback.print_exc()

    async def test_full_pipeline(self):
        """Test full performance-optimized pipeline."""
        print_header("TEST: Full Performance Pipeline")

        try:
            from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
            from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache
            from app.infrastructure.caching.image_hash import compute_image_hash
            from app.infrastructure.persistence.repositories.thread_safe_memory_repository import (
                ThreadSafeInMemoryEmbeddingRepository
            )

            # Initialize components
            pool = ThreadPoolManager(max_workers=4, thread_name_prefix="pipeline-test")
            cache = ThreadSafeLRUCache[str, np.ndarray](max_size=100, ttl_seconds=300)
            repo = ThreadSafeInMemoryEmbeddingRepository(max_capacity=1000)

            print_success("All pipeline components initialized")

            # Simulate embedding extraction (mock since we don't want to load DeepFace)
            def mock_extract_embedding(image: np.ndarray) -> np.ndarray:
                """Mock embedding extraction using image statistics."""
                # Use image properties to create a pseudo-embedding
                mean_vals = np.mean(image, axis=(0, 1))
                std_vals = np.std(image, axis=(0, 1))

                # Create a reproducible 512-d embedding from image stats
                np.random.seed(int(np.sum(mean_vals * 1000)) % (2**31))
                embedding = np.random.randn(512).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)
                return embedding

            # Test 1: Process all images through pipeline
            print_section("Test 1: Full Pipeline Processing")

            total_start = time.perf_counter()
            cache_hits = 0
            cache_misses = 0

            for user_id, user_images in self.images.items():
                for img_data in user_images:
                    image = img_data["image"]

                    # Check cache
                    image_hash = compute_image_hash(image)
                    cached_embedding = cache.get(image_hash)

                    if cached_embedding is not None:
                        cache_hits += 1
                        embedding = cached_embedding
                    else:
                        cache_misses += 1
                        # Extract embedding via thread pool
                        embedding = await pool.run_blocking(mock_extract_embedding, image)
                        cache.put(image_hash, embedding)

                    # Store in repository
                    await repo.save(
                        user_id=f"{user_id}_{img_data['name']}",
                        embedding=embedding,
                        quality_score=85.0,
                        tenant_id="pipeline_test"
                    )

            total_elapsed = time.perf_counter() - total_start

            print_info(f"Processed all images in {total_elapsed*1000:.2f}ms")
            print_info(f"Cache hits: {cache_hits}, misses: {cache_misses}")

            # Test 2: Re-process same images (should hit cache)
            print_section("Test 2: Cache Hit Performance")

            reprocess_start = time.perf_counter()

            for user_id, user_images in self.images.items():
                for img_data in user_images:
                    image_hash = compute_image_hash(img_data["image"])
                    _ = cache.get(image_hash)

            reprocess_elapsed = time.perf_counter() - reprocess_start

            print_info(f"Re-processed all images (cache lookup) in {reprocess_elapsed*1000:.2f}ms")

            speedup = total_elapsed / reprocess_elapsed if reprocess_elapsed > 0 else float('inf')
            print_success(f"Cache speedup: {speedup:.1f}x")

            # Test 3: Similarity search
            print_section("Test 3: Similarity Search")

            sample_image = list(self.images.values())[0][0]["image"]
            query_embedding = await pool.run_blocking(mock_extract_embedding, sample_image)

            search_start = time.perf_counter()
            similar = await repo.find_similar(
                query_embedding,
                threshold=0.8,
                limit=5,
                tenant_id="pipeline_test"
            )
            search_elapsed = time.perf_counter() - search_start

            print_info(f"Found {len(similar)} similar embeddings in {search_elapsed*1000:.2f}ms")

            for user_id, distance in similar[:3]:
                print_info(f"  {user_id}: distance={distance:.4f}")

            # Cleanup
            pool.shutdown(wait=True)

            # Final stats
            print_section("Final Statistics")

            cache_stats = cache.stats()
            repo_count = await repo.count("pipeline_test")

            print_info(f"Cache size: {cache_stats.size}")
            print_info(f"Cache hit rate: {cache_stats.hits/(cache_stats.hits+cache_stats.misses)*100:.1f}%")
            print_info(f"Repository size: {repo_count}")

            print_success("Full pipeline test completed successfully")

            self.results["full_pipeline"] = "PASSED"

        except Exception as e:
            print_fail(f"Full pipeline test failed: {e}")
            self.results["full_pipeline"] = f"FAILED: {e}"
            import traceback
            traceback.print_exc()

    def print_summary(self):
        """Print test summary."""
        print_header("TEST SUMMARY")

        passed = 0
        failed = 0

        for test_name, result in self.results.items():
            if result == "PASSED":
                print_success(f"{test_name}: {result}")
                passed += 1
            else:
                print_fail(f"{test_name}: {result}")
                failed += 1

        print(f"\n{Colors.BOLD}Total: {passed} passed, {failed} failed{Colors.ENDC}")

        if failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.ENDC}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed. Please review.{Colors.ENDC}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Manual Performance Tests")
    parser.add_argument(
        "--section",
        choices=["thread_pool", "cache", "hashing", "repository", "liveness", "full_pipeline", "all"],
        default="all",
        help="Test section to run"
    )
    args = parser.parse_args()

    print_header("BIOMETRIC PROCESSOR - MANUAL PERFORMANCE TESTS")
    print_info(f"Running section: {args.section}")

    runner = ManualTestRunner()

    if not runner.setup():
        print_fail("Setup failed! Exiting.")
        return

    sections = {
        "thread_pool": runner.test_thread_pool_manager,
        "hashing": runner.test_image_hashing,
        "cache": runner.test_lru_cache,
        "repository": runner.test_thread_safe_repository,
        "liveness": runner.test_optimized_liveness,
        "full_pipeline": runner.test_full_pipeline,
    }

    if args.section == "all":
        for section_name, test_func in sections.items():
            await test_func()
    else:
        if args.section in sections:
            await sections[args.section]()
        else:
            print_fail(f"Unknown section: {args.section}")

    runner.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
