"""Unit tests for InMemoryEmbeddingRepository."""

import pytest
import numpy as np
from datetime import datetime, timedelta

from app.infrastructure.persistence.repositories.memory_embedding_repository import (
    InMemoryEmbeddingRepository
)
from app.domain.exceptions.repository_errors import RepositoryError


class TestInMemoryEmbeddingRepository:
    """Test InMemoryEmbeddingRepository."""

    @pytest.mark.asyncio
    async def test_save_new_embedding(self):
        """Test saving new embedding."""
        repo = InMemoryEmbeddingRepository()

        embedding = np.random.randn(128).astype(np.float32)
        await repo.save("user_1", embedding, quality_score=85.0)

        # Verify it exists
        assert await repo.exists("user_1") is True

    @pytest.mark.asyncio
    async def test_save_with_tenant_id(self):
        """Test saving embedding with tenant ID."""
        repo = InMemoryEmbeddingRepository()

        embedding = np.random.randn(128).astype(np.float32)
        await repo.save("user_1", embedding, quality_score=85.0, tenant_id="tenant_a")

        assert await repo.exists("user_1", tenant_id="tenant_a") is True
        assert await repo.exists("user_1", tenant_id="tenant_b") is False

    @pytest.mark.asyncio
    async def test_save_update_existing(self):
        """Test updating existing embedding."""
        repo = InMemoryEmbeddingRepository()

        # Save initial embedding
        emb1 = np.ones(128, dtype=np.float32)
        await repo.save("user_1", emb1, quality_score=80.0)

        # Update with new embedding
        emb2 = np.ones(128, dtype=np.float32) * 2
        await repo.save("user_1", emb2, quality_score=90.0)

        # Retrieve and verify it's updated
        retrieved = await repo.find_by_user_id("user_1")
        assert np.array_equal(retrieved, emb2)

    @pytest.mark.asyncio
    async def test_find_by_user_id_exists(self):
        """Test finding existing embedding by user ID."""
        repo = InMemoryEmbeddingRepository()

        original_embedding = np.random.randn(128).astype(np.float32)
        await repo.save("user_1", original_embedding, quality_score=85.0)

        # Find embedding
        found_embedding = await repo.find_by_user_id("user_1")

        assert found_embedding is not None
        assert np.array_equal(found_embedding, original_embedding)

    @pytest.mark.asyncio
    async def test_find_by_user_id_not_exists(self):
        """Test finding non-existent embedding."""
        repo = InMemoryEmbeddingRepository()

        found = await repo.find_by_user_id("nonexistent_user")

        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_user_id_with_tenant(self):
        """Test finding embedding with tenant isolation."""
        repo = InMemoryEmbeddingRepository()

        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        await repo.save("user_1", emb1, quality_score=85.0, tenant_id="tenant_a")
        await repo.save("user_1", emb2, quality_score=90.0, tenant_id="tenant_b")

        # Should get different embeddings for different tenants
        found_a = await repo.find_by_user_id("user_1", tenant_id="tenant_a")
        found_b = await repo.find_by_user_id("user_1", tenant_id="tenant_b")

        assert not np.array_equal(found_a, found_b)
        assert np.array_equal(found_a, emb1)
        assert np.array_equal(found_b, emb2)

    @pytest.mark.asyncio
    async def test_find_similar_single_match(self):
        """Test finding similar embeddings."""
        repo = InMemoryEmbeddingRepository()

        # Save embeddings
        emb1 = np.random.randn(128).astype(np.float32)
        emb_similar = emb1 + np.random.randn(128).astype(np.float32) * 0.01  # Very similar

        await repo.save("user_1", emb1, quality_score=85.0)
        await repo.save("user_2", emb_similar, quality_score=90.0)

        # Find similar to emb1
        matches = await repo.find_similar(emb1, threshold=0.5, limit=5)

        # Should find at least user_1 (itself)
        assert len(matches) >= 1
        assert any(user_id == "user_1" for user_id, _ in matches)

    @pytest.mark.asyncio
    async def test_find_similar_multiple_matches(self):
        """Test finding multiple similar embeddings."""
        repo = InMemoryEmbeddingRepository()

        # Create base embedding
        base = np.random.randn(128).astype(np.float32)

        # Save similar embeddings
        for i in range(5):
            emb = base + np.random.randn(128).astype(np.float32) * 0.1
            await repo.save(f"user_{i}", emb, quality_score=85.0)

        # Find similar
        matches = await repo.find_similar(base, threshold=0.6, limit=10)

        # Should find all 5 similar embeddings
        assert len(matches) == 5

    @pytest.mark.asyncio
    async def test_find_similar_with_limit(self):
        """Test that find_similar respects limit."""
        repo = InMemoryEmbeddingRepository()

        base = np.random.randn(128).astype(np.float32)

        # Save 10 similar embeddings
        for i in range(10):
            emb = base + np.random.randn(128).astype(np.float32) * 0.1
            await repo.save(f"user_{i}", emb, quality_score=85.0)

        # Find with limit=3
        matches = await repo.find_similar(base, threshold=0.8, limit=3)

        # Should respect limit
        assert len(matches) <= 3

    @pytest.mark.asyncio
    async def test_find_similar_sorted_by_distance(self):
        """Test that results are sorted by distance."""
        repo = InMemoryEmbeddingRepository()

        base = np.random.randn(128).astype(np.float32)

        # Save similar embeddings
        for i in range(5):
            emb = base + np.random.randn(128).astype(np.float32) * 0.1
            await repo.save(f"user_{i}", emb, quality_score=85.0)

        # Find similar
        matches = await repo.find_similar(base, threshold=0.8, limit=10)

        # Distances should be in ascending order
        distances = [distance for _, distance in matches]
        assert distances == sorted(distances)

    @pytest.mark.asyncio
    async def test_find_similar_with_tenant_filter(self):
        """Test that find_similar filters by tenant."""
        repo = InMemoryEmbeddingRepository()

        base = np.random.randn(128).astype(np.float32)

        # Save embeddings for different tenants
        for i in range(3):
            emb = base + np.random.randn(128).astype(np.float32) * 0.1
            await repo.save(f"user_{i}", emb, quality_score=85.0, tenant_id="tenant_a")

        for i in range(3, 6):
            emb = base + np.random.randn(128).astype(np.float32) * 0.1
            await repo.save(f"user_{i}", emb, quality_score=85.0, tenant_id="tenant_b")

        # Find similar for tenant_a only
        matches = await repo.find_similar(base, threshold=0.8, limit=10, tenant_id="tenant_a")

        # Should only find tenant_a embeddings
        assert len(matches) == 3
        assert all(user_id.startswith("user_") and int(user_id.split("_")[1]) < 3
                   for user_id, _ in matches)

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        """Test deleting existing embedding."""
        repo = InMemoryEmbeddingRepository()

        embedding = np.random.randn(128).astype(np.float32)
        await repo.save("user_1", embedding, quality_score=85.0)

        # Delete
        deleted = await repo.delete("user_1")

        assert deleted is True
        assert await repo.exists("user_1") is False

    @pytest.mark.asyncio
    async def test_delete_non_existing(self):
        """Test deleting non-existent embedding."""
        repo = InMemoryEmbeddingRepository()

        deleted = await repo.delete("nonexistent_user")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_with_tenant(self):
        """Test deleting with tenant ID."""
        repo = InMemoryEmbeddingRepository()

        embedding = np.random.randn(128).astype(np.float32)
        await repo.save("user_1", embedding, quality_score=85.0, tenant_id="tenant_a")
        await repo.save("user_1", embedding, quality_score=85.0, tenant_id="tenant_b")

        # Delete from tenant_a only
        await repo.delete("user_1", tenant_id="tenant_a")

        assert await repo.exists("user_1", tenant_id="tenant_a") is False
        assert await repo.exists("user_1", tenant_id="tenant_b") is True

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test exists returns True for existing embedding."""
        repo = InMemoryEmbeddingRepository()

        embedding = np.random.randn(128).astype(np.float32)
        await repo.save("user_1", embedding, quality_score=85.0)

        assert await repo.exists("user_1") is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test exists returns False for non-existent embedding."""
        repo = InMemoryEmbeddingRepository()

        assert await repo.exists("nonexistent_user") is False

    @pytest.mark.asyncio
    async def test_count_total(self):
        """Test counting total embeddings."""
        repo = InMemoryEmbeddingRepository()

        # Save multiple embeddings
        for i in range(5):
            emb = np.random.randn(128).astype(np.float32)
            await repo.save(f"user_{i}", emb, quality_score=85.0)

        count = await repo.count()

        assert count == 5

    @pytest.mark.asyncio
    async def test_count_by_tenant(self):
        """Test counting embeddings by tenant."""
        repo = InMemoryEmbeddingRepository()

        # Save for different tenants
        for i in range(3):
            emb = np.random.randn(128).astype(np.float32)
            await repo.save(f"user_{i}", emb, quality_score=85.0, tenant_id="tenant_a")

        for i in range(3, 7):
            emb = np.random.randn(128).astype(np.float32)
            await repo.save(f"user_{i}", emb, quality_score=85.0, tenant_id="tenant_b")

        count_a = await repo.count(tenant_id="tenant_a")
        count_b = await repo.count(tenant_id="tenant_b")

        assert count_a == 3
        assert count_b == 4

    def test_clear(self):
        """Test clearing all embeddings."""
        repo = InMemoryEmbeddingRepository()

        # Save some embeddings (synchronous for this test)
        repo._embeddings[("user_1", None)] = {
            "embedding": np.random.randn(128).astype(np.float32),
            "quality_score": 85.0,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        }
        repo._embeddings[("user_2", None)] = {
            "embedding": np.random.randn(128).astype(np.float32),
            "quality_score": 90.0,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        }

        # Clear
        repo.clear()

        assert len(repo._embeddings) == 0

    def test_cosine_distance_identical(self):
        """Test cosine distance calculation for identical embeddings."""
        emb = np.random.randn(128).astype(np.float32)

        distance = InMemoryEmbeddingRepository._cosine_distance(emb, emb)

        assert distance < 0.01  # Should be nearly 0

    def test_cosine_distance_orthogonal(self):
        """Test cosine distance for orthogonal embeddings."""
        emb1 = np.zeros(128, dtype=np.float32)
        emb1[0] = 1.0

        emb2 = np.zeros(128, dtype=np.float32)
        emb2[1] = 1.0

        distance = InMemoryEmbeddingRepository._cosine_distance(emb1, emb2)

        assert 0.99 < distance <= 1.0

    def test_cosine_distance_clamped(self):
        """Test that cosine distance is clamped to [0, 1]."""
        emb1 = np.random.randn(128).astype(np.float32)
        emb2 = np.random.randn(128).astype(np.float32)

        distance = InMemoryEmbeddingRepository._cosine_distance(emb1, emb2)

        assert 0.0 <= distance <= 1.0

    @pytest.mark.asyncio
    async def test_save_creates_copy(self):
        """Test that save creates a copy of the embedding."""
        repo = InMemoryEmbeddingRepository()

        original = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        await repo.save("user_1", original, quality_score=85.0)

        # Modify original
        original[0] = 999.0

        # Retrieved should not be modified
        retrieved = await repo.find_by_user_id("user_1")
        assert retrieved[0] == 1.0
        assert retrieved[0] != 999.0

    @pytest.mark.asyncio
    async def test_find_returns_copy(self):
        """Test that find returns a copy, not reference."""
        repo = InMemoryEmbeddingRepository()

        embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        await repo.save("user_1", embedding, quality_score=85.0)

        # Find and modify
        found = await repo.find_by_user_id("user_1")
        found[0] = 999.0

        # Find again - should not be modified
        found_again = await repo.find_by_user_id("user_1")
        assert found_again[0] == 1.0
        assert found_again[0] != 999.0
