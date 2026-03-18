"""
Critical API Integration Tests

Tests the most critical API endpoints with real database integration:
- Health checks
- Enrollment (single and multi-image)
- Search (1:N)
- Verification (1:1)
- Database persistence
- Model compatibility (512-dimensional embeddings)
- Quality threshold validation

These tests ensure the system works end-to-end and catch issues early.
"""

import base64
from io import BytesIO

import numpy as np
import pytest
from PIL import Image
from httpx import AsyncClient
from app.main import app
from app.core.container import get_embedding_repository
from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
    PgVectorEmbeddingRepository,
)


# Test fixtures
@pytest.fixture
async def client():
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def embedding_repo():
    """Get embedding repository instance."""
    repo = get_embedding_repository()
    yield repo
    # Cleanup after tests
    if isinstance(repo, PgVectorEmbeddingRepository):
        try:
            # Clean up test data
            await repo.delete_by_user_id("test_user_critical", tenant_id="test_tenant")
            await repo.delete_by_user_id("test_user_search_1", tenant_id="test_tenant")
            await repo.delete_by_user_id("test_user_search_2", tenant_id="test_tenant")
        except Exception:
            pass  # Cleanup errors are non-critical


@pytest.fixture
def sample_face_image() -> bytes:
    """
    Create a sample face image for testing.
    Returns a valid image as bytes that can pass basic checks.
    """
    # Create a 640x480 RGB image with a simple pattern
    img = Image.new("RGB", (640, 480), color=(128, 128, 128))

    # Add some variation to help with blur detection
    pixels = img.load()
    for i in range(0, 640, 20):
        for j in range(0, 480, 20):
            if (i + j) % 40 == 0:
                pixels[i, j] = (255, 255, 255)

    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


@pytest.fixture
def sample_face_base64(sample_face_image) -> str:
    """Convert sample image to base64 string."""
    return base64.b64encode(sample_face_image).decode("utf-8")


class TestHealthEndpoints:
    """Test all health check endpoints."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self, client: AsyncClient):
        """Test GET /api/v1/health - basic health check."""
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, client: AsyncClient):
        """Test GET /api/v1/health/detailed - detailed health with all components."""
        response = await client.get("/api/v1/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

        # Verify critical components are checked
        components = data["components"]
        assert "database" in components
        assert "redis" in components
        assert "models" in components

    @pytest.mark.asyncio
    async def test_liveness_probe(self, client: AsyncClient):
        """Test GET /api/v1/health/live - Kubernetes liveness probe."""
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_probe(self, client: AsyncClient):
        """Test GET /api/v1/health/ready - Kubernetes readiness probe."""
        response = await client.get("/api/v1/health/ready")
        # Should be 200 if all dependencies are ready, 503 otherwise
        assert response.status_code in [200, 503]


class TestEnrollmentEndpoint:
    """Test face enrollment endpoints."""

    @pytest.mark.asyncio
    async def test_enroll_success(
        self,
        client: AsyncClient,
        sample_face_image: bytes,
        embedding_repo,
    ):
        """Test successful face enrollment with database persistence."""
        # Clean up any existing data first
        if isinstance(embedding_repo, PgVectorEmbeddingRepository):
            await embedding_repo.delete_by_user_id(
                "test_user_enroll_success", tenant_id="test_tenant"
            )

        # Prepare multipart form data
        files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}
        data = {
            "user_id": "test_user_enroll_success",
            "tenant_id": "test_tenant",
        }

        response = await client.post("/api/v1/enroll", files=files, data=data)

        # Verify API response
        assert response.status_code == 200, f"Enrollment failed: {response.text}"
        result = response.json()

        assert result["success"] is True
        assert result["user_id"] == "test_user_enroll_success"
        assert "embedding_id" in result
        assert "quality_score" in result

        # Verify database persistence
        stored = await embedding_repo.get_by_user_id(
            "test_user_enroll_success", tenant_id="test_tenant"
        )
        assert stored is not None
        assert stored.user_id == "test_user_enroll_success"
        assert stored.tenant_id == "test_tenant"

        # Verify embedding dimension (FaceNet = 512)
        assert len(stored.embedding) == 512, (
            f"Embedding dimension mismatch: expected 512, got {len(stored.embedding)}"
        )

        # Cleanup
        await embedding_repo.delete_by_user_id(
            "test_user_enroll_success", tenant_id="test_tenant"
        )

    @pytest.mark.asyncio
    async def test_enroll_missing_image(self, client: AsyncClient):
        """Test enrollment fails without image."""
        data = {
            "user_id": "test_user",
            "tenant_id": "test_tenant",
        }

        response = await client.post("/api/v1/enroll", data=data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_enroll_missing_user_id(
        self, client: AsyncClient, sample_face_image: bytes
    ):
        """Test enrollment fails without user_id."""
        files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}
        data = {"tenant_id": "test_tenant"}

        response = await client.post("/api/v1/enroll", files=files, data=data)
        assert response.status_code == 422  # Validation error


class TestSearchEndpoint:
    """Test face search (1:N) endpoints."""

    @pytest.mark.asyncio
    async def test_search_success(
        self,
        client: AsyncClient,
        sample_face_image: bytes,
        embedding_repo,
    ):
        """Test successful face search after enrollment."""
        # Enroll a test face first
        files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}
        data = {
            "user_id": "test_user_search_success",
            "tenant_id": "test_tenant",
        }

        enroll_response = await client.post("/api/v1/enroll", files=files, data=data)
        assert enroll_response.status_code == 200, f"Enrollment failed: {enroll_response.text}"

        # Now search for the same face
        search_files = {"image": ("search.jpg", sample_face_image, "image/jpeg")}
        search_data = {"tenant_id": "test_tenant", "threshold": 0.5, "top_k": 5}

        search_response = await client.post(
            "/api/v1/search", files=search_files, data=search_data
        )

        assert search_response.status_code == 200, f"Search failed: {search_response.text}"
        result = search_response.json()

        assert "matches" in result
        assert "total_searched" in result
        assert result["total_searched"] >= 1  # At least our enrolled face

        # Cleanup
        await embedding_repo.delete_by_user_id(
            "test_user_search_success", tenant_id="test_tenant"
        )

    @pytest.mark.asyncio
    async def test_search_empty_database(
        self, client: AsyncClient, sample_face_image: bytes
    ):
        """Test search returns empty results when database is empty."""
        # Use a unique tenant to ensure empty database
        files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}
        data = {"tenant_id": "empty_tenant_unique_12345", "threshold": 0.5, "top_k": 5}

        response = await client.post("/api/v1/search", files=files, data=data)

        assert response.status_code == 200
        result = response.json()

        assert result["matches"] == [] or len(result["matches"]) == 0
        assert result["total_searched"] == 0


class TestVerificationEndpoint:
    """Test face verification (1:1) endpoints."""

    @pytest.mark.asyncio
    async def test_verify_success(
        self,
        client: AsyncClient,
        sample_face_image: bytes,
        embedding_repo,
    ):
        """Test successful face verification after enrollment."""
        # Enroll a test face first
        enroll_files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}
        enroll_data = {
            "user_id": "test_user_verify",
            "tenant_id": "test_tenant",
        }

        enroll_response = await client.post(
            "/api/v1/enroll", files=enroll_files, data=enroll_data
        )
        assert enroll_response.status_code == 200

        # Now verify against the same face
        verify_files = {"image": ("verify.jpg", sample_face_image, "image/jpeg")}
        verify_data = {
            "user_id": "test_user_verify",
            "tenant_id": "test_tenant",
            "threshold": 0.5,
        }

        verify_response = await client.post(
            "/api/v1/verify", files=verify_files, data=verify_data
        )

        assert verify_response.status_code == 200
        result = verify_response.json()

        assert "is_match" in result
        assert "confidence" in result
        assert "user_id" in result
        assert result["user_id"] == "test_user_verify"

        # Cleanup
        await embedding_repo.delete_by_user_id(
            "test_user_verify", tenant_id="test_tenant"
        )


class TestDatabasePersistence:
    """Test database persistence and compatibility."""

    @pytest.mark.asyncio
    async def test_embedding_dimension_validation(self, embedding_repo):
        """Test that only 512-dimensional embeddings are accepted."""
        from app.domain.entities.embedding import Embedding

        # Create a test embedding with correct dimension
        embedding_512 = Embedding(
            id="test_embed_512",
            user_id="test_user_dimension",
            tenant_id="test_tenant",
            embedding=np.random.rand(512).tolist(),
            quality_score=85.0,
        )

        # Save should succeed
        saved = await embedding_repo.save(embedding_512)
        assert saved is not None
        assert len(saved.embedding) == 512

        # Retrieve and verify dimension
        retrieved = await embedding_repo.get_by_user_id(
            "test_user_dimension", tenant_id="test_tenant"
        )
        assert retrieved is not None
        assert len(retrieved.embedding) == 512

        # Cleanup
        await embedding_repo.delete_by_user_id(
            "test_user_dimension", tenant_id="test_tenant"
        )

    @pytest.mark.asyncio
    async def test_persistence_across_restart_simulation(self, embedding_repo):
        """Test that embeddings persist (simulating API restart)."""
        from app.domain.entities.embedding import Embedding

        user_id = "test_user_persistence"
        tenant_id = "test_tenant"

        # Save an embedding
        embedding = Embedding(
            id="test_embed_persist",
            user_id=user_id,
            tenant_id=tenant_id,
            embedding=np.random.rand(512).tolist(),
            quality_score=80.0,
        )

        await embedding_repo.save(embedding)

        # Simulate "restart" by getting a new repository instance
        # (In real scenario, this would be after API restart)
        repo_after_restart = get_embedding_repository()

        # Verify data still exists
        retrieved = await repo_after_restart.get_by_user_id(user_id, tenant_id=tenant_id)
        assert retrieved is not None
        assert retrieved.user_id == user_id
        assert retrieved.tenant_id == tenant_id
        assert len(retrieved.embedding) == 512

        # Cleanup
        await embedding_repo.delete_by_user_id(user_id, tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_count_embeddings(self, embedding_repo):
        """Test counting embeddings in database."""
        # Get initial count
        initial_count = await embedding_repo.count(tenant_id="test_tenant_count")

        # Add test embeddings
        from app.domain.entities.embedding import Embedding

        for i in range(3):
            embedding = Embedding(
                id=f"test_count_{i}",
                user_id=f"test_user_count_{i}",
                tenant_id="test_tenant_count",
                embedding=np.random.rand(512).tolist(),
                quality_score=80.0,
            )
            await embedding_repo.save(embedding)

        # Verify count increased
        new_count = await embedding_repo.count(tenant_id="test_tenant_count")
        assert new_count == initial_count + 3

        # Cleanup
        for i in range(3):
            await embedding_repo.delete_by_user_id(
                f"test_user_count_{i}", tenant_id="test_tenant_count"
            )


class TestQualityThresholds:
    """Test quality threshold validation."""

    @pytest.mark.asyncio
    async def test_quality_endpoint(self, client: AsyncClient, sample_face_image: bytes):
        """Test POST /api/v1/quality/analyze endpoint."""
        files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}

        response = await client.post("/api/v1/quality/analyze", files=files)

        # Should return quality analysis
        assert response.status_code in [200, 400]  # 400 if quality too low

        if response.status_code == 200:
            result = response.json()
            assert "quality_score" in result
            assert "issues" in result


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_image_format(self, client: AsyncClient):
        """Test enrollment rejects invalid image format."""
        # Send plain text instead of image
        invalid_file = b"This is not an image"
        files = {"image": ("test.txt", invalid_file, "text/plain")}
        data = {"user_id": "test_user", "tenant_id": "test_tenant"}

        response = await client.post("/api/v1/enroll", files=files, data=data)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_missing_tenant_id_in_search(
        self, client: AsyncClient, sample_face_image: bytes
    ):
        """Test search handles missing tenant_id gracefully."""
        files = {"image": ("test.jpg", sample_face_image, "image/jpeg")}
        data = {"threshold": 0.5, "top_k": 5}  # No tenant_id

        response = await client.post("/api/v1/search", files=files, data=data)
        # Should either work (tenant_id optional) or return validation error
        assert response.status_code in [200, 422]


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
