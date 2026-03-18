"""Unit tests for Phase 2 infrastructure components."""

import pytest
import time
from datetime import datetime, timedelta

from app.domain.entities.api_key import APIKey


# ============================================================================
# API Key Entity Tests
# ============================================================================


class TestAPIKeyEntity:
    """Test APIKey entity."""

    def test_generate_key_length(self):
        """Test that generated keys have correct length."""
        key = APIKey.generate_key()
        assert len(key) == 64  # 32 bytes hex encoded

    def test_hash_key_produces_consistent_hash(self):
        """Test that hashing is consistent."""
        key = "test_key_12345"
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)
        assert hash1 == hash2

    def test_hash_key_produces_different_hash_for_different_keys(self):
        """Test that different keys produce different hashes."""
        hash1 = APIKey.hash_key("key1")
        hash2 = APIKey.hash_key("key2")
        assert hash1 != hash2

    def test_get_prefix(self):
        """Test key prefix extraction."""
        key = "abcdefghijklmnop"
        prefix = APIKey.get_prefix(key)
        assert prefix == "abcdefgh"

    def test_create_new_returns_entity_and_key(self):
        """Test creating new API key entity."""
        entity, plaintext_key = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
            scopes=["read", "write"],
            tier="premium",
        )

        assert entity.name == "Test Key"
        assert entity.tenant_id == "tenant1"
        assert entity.scopes == ["read", "write"]
        assert entity.tier == "premium"
        assert entity.is_active is True
        assert len(plaintext_key) == 64
        assert entity.key_prefix == plaintext_key[:8]

    def test_verify_correct_key(self):
        """Test verifying correct key."""
        entity, plaintext_key = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
        )
        assert entity.verify(plaintext_key) is True

    def test_verify_incorrect_key(self):
        """Test verifying incorrect key."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
        )
        assert entity.verify("wrong_key") is False

    def test_is_expired_not_set(self):
        """Test is_expired when no expiration set."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
        )
        assert entity.is_expired() is False

    def test_is_expired_future_date(self):
        """Test is_expired with future expiration."""
        future = datetime.utcnow() + timedelta(days=1)
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
            expires_at=future,
        )
        assert entity.is_expired() is False

    def test_is_expired_past_date(self):
        """Test is_expired with past expiration."""
        past = datetime.utcnow() - timedelta(days=1)
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
            expires_at=past,
        )
        assert entity.is_expired() is True

    def test_is_valid_active_not_expired(self):
        """Test is_valid for active, non-expired key."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
        )
        assert entity.is_valid() is True

    def test_is_valid_inactive(self):
        """Test is_valid for inactive key."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
        )
        entity.is_active = False
        assert entity.is_valid() is False

    def test_has_scope_true(self):
        """Test has_scope returns true for valid scope."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
            scopes=["read", "write"],
        )
        assert entity.has_scope("read") is True
        assert entity.has_scope("write") is True

    def test_has_scope_false(self):
        """Test has_scope returns false for invalid scope."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
            scopes=["read"],
        )
        assert entity.has_scope("admin") is False

    def test_has_scope_wildcard(self):
        """Test has_scope with wildcard scope."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
            scopes=["*"],
        )
        assert entity.has_scope("anything") is True


# ============================================================================
# In-Memory API Key Repository Tests
# ============================================================================


class TestInMemoryAPIKeyRepository:
    """Test InMemoryAPIKeyRepository."""

    @pytest.fixture
    def repository(self):
        """Create repository fixture."""
        from app.infrastructure.auth.memory_api_key_repository import (
            InMemoryAPIKeyRepository,
        )
        return InMemoryAPIKeyRepository()

    @pytest.fixture
    def sample_api_key(self):
        """Create sample API key fixture."""
        entity, _ = APIKey.create_new(
            name="Test Key",
            tenant_id="tenant1",
        )
        return entity

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, repository, sample_api_key):
        """Test saving and retrieving by ID."""
        await repository.save(sample_api_key)
        found = await repository.find_by_id(sample_api_key.id)
        assert found is not None
        assert found.id == sample_api_key.id

    @pytest.mark.asyncio
    async def test_find_by_key_hash(self, repository, sample_api_key):
        """Test finding by key hash."""
        await repository.save(sample_api_key)
        found = await repository.find_by_key_hash(sample_api_key.key_hash)
        assert found is not None
        assert found.id == sample_api_key.id

    @pytest.mark.asyncio
    async def test_find_by_prefix(self, repository, sample_api_key):
        """Test finding by prefix."""
        await repository.save(sample_api_key)
        found = await repository.find_by_prefix(sample_api_key.key_prefix)
        assert found is not None
        assert found.id == sample_api_key.id

    @pytest.mark.asyncio
    async def test_find_by_tenant(self, repository, sample_api_key):
        """Test finding by tenant."""
        await repository.save(sample_api_key)
        keys = await repository.find_by_tenant("tenant1")
        assert len(keys) == 1
        assert keys[0].id == sample_api_key.id

    @pytest.mark.asyncio
    async def test_deactivate(self, repository, sample_api_key):
        """Test deactivating a key."""
        await repository.save(sample_api_key)
        result = await repository.deactivate(sample_api_key.id)
        assert result is True

        found = await repository.find_by_id(sample_api_key.id)
        assert found.is_active is False

    @pytest.mark.asyncio
    async def test_delete(self, repository, sample_api_key):
        """Test deleting a key."""
        await repository.save(sample_api_key)
        result = await repository.delete(sample_api_key.id)
        assert result is True

        found = await repository.find_by_id(sample_api_key.id)
        assert found is None


# ============================================================================
# In-Memory Rate Limit Storage Tests
# ============================================================================


class TestInMemoryRateLimitStorage:
    """Test InMemoryRateLimitStorage."""

    @pytest.fixture
    def storage(self):
        """Create storage fixture."""
        from app.infrastructure.rate_limit.memory_storage import (
            InMemoryRateLimitStorage,
        )
        return InMemoryRateLimitStorage()

    @pytest.mark.asyncio
    async def test_increment_first_request(self, storage):
        """Test first request increment."""
        info = await storage.increment("test_key", limit=10, window_seconds=60)
        assert info.limit == 10
        assert info.remaining == 9

    @pytest.mark.asyncio
    async def test_increment_multiple_requests(self, storage):
        """Test multiple request increments."""
        for i in range(5):
            info = await storage.increment("test_key", limit=10, window_seconds=60)

        assert info.remaining == 5

    @pytest.mark.asyncio
    async def test_increment_exceeds_limit(self, storage):
        """Test exceeding limit."""
        for i in range(12):
            info = await storage.increment("test_key", limit=10, window_seconds=60)

        assert info.remaining == 0

    @pytest.mark.asyncio
    async def test_reset(self, storage):
        """Test resetting a key."""
        await storage.increment("test_key", limit=10, window_seconds=60)
        await storage.reset("test_key")

        info = await storage.get("test_key")
        assert info is not None
        # After reset, remaining should be at limit
        assert info.remaining >= 0


# ============================================================================
# Metrics Collector Tests
# ============================================================================


class TestMetricsCollector:
    """Test MetricsCollector."""

    @pytest.fixture
    def collector(self):
        """Create metrics collector fixture."""
        from app.core.metrics.prometheus import MetricsCollector
        return MetricsCollector()

    def test_init(self, collector):
        """Test initialization."""
        collector.init(
            app_name="Test App",
            version="1.0.0",
            environment="test",
        )
        assert collector._initialized is True

    def test_track_request_context(self, collector):
        """Test request tracking context manager."""
        with collector.track_request(method="GET", endpoint="/test"):
            # Simulate request processing
            time.sleep(0.01)

    def test_record_face_operation(self, collector):
        """Test recording face operations."""
        collector.record_face_operation(operation="detect", success=True)
        collector.record_face_operation(operation="enroll", success=False)

    def test_record_error(self, collector):
        """Test recording errors."""
        collector.record_error(error_type="FaceNotDetectedError", endpoint="/enroll")

    def test_get_metrics(self, collector):
        """Test getting metrics output."""
        metrics = collector.get_metrics()
        assert isinstance(metrics, bytes)
        assert len(metrics) > 0


# ============================================================================
# Rate Limit Storage Factory Tests
# ============================================================================


class TestRateLimitStorageFactory:
    """Test RateLimitStorageFactory."""

    def test_create_memory_backend(self):
        """Test creating memory backend."""
        from app.infrastructure.rate_limit.storage_factory import (
            RateLimitStorageFactory,
        )
        storage = RateLimitStorageFactory.create(backend="memory")
        assert storage is not None

    def test_create_redis_backend_requires_url(self):
        """Test that redis backend requires URL."""
        from app.infrastructure.rate_limit.storage_factory import (
            RateLimitStorageFactory,
        )
        with pytest.raises(ValueError) as exc_info:
            RateLimitStorageFactory.create(backend="redis")
        assert "redis_url is required" in str(exc_info.value)

    def test_create_unknown_backend_raises_error(self):
        """Test that unknown backend raises error."""
        from app.infrastructure.rate_limit.storage_factory import (
            RateLimitStorageFactory,
        )
        with pytest.raises(ValueError) as exc_info:
            RateLimitStorageFactory.create(backend="unknown")
        assert "Unknown storage backend" in str(exc_info.value)
