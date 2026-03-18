"""End-to-end tests for complete biometric workflows.

These tests verify the full flow from API request through all layers
to storage and back, using real components with minimal mocking.
"""

import io
import sys
import tempfile
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

# Mock DeepFace before imports
sys.modules["deepface"] = Mock()
sys.modules["deepface.DeepFace"] = Mock()

from app.core.container import (
    get_check_liveness_use_case,
    get_enroll_face_use_case,
    get_file_storage,
    get_verify_face_use_case,
)
from app.domain.entities.face_detection import FaceDetectionResult
from app.infrastructure.persistence.repositories.memory_embedding_repository import (
    InMemoryEmbeddingRepository,
)
from app.infrastructure.storage.local_file_storage import LocalFileStorage
from app.main import app


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for file storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def client():
    """Create test client with clean state."""
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def real_image():
    """Create a realistic test image (grayscale face-like)."""
    # Create 200x200 image with face-like features
    img = np.zeros((200, 200, 3), dtype=np.uint8)

    # Add some structure to simulate a face
    cv2.circle(img, (100, 100), 80, (180, 180, 180), -1)  # Head
    cv2.circle(img, (75, 85), 10, (50, 50, 50), -1)  # Left eye
    cv2.circle(img, (125, 85), 10, (50, 50, 50), -1)  # Right eye
    cv2.ellipse(img, (100, 130), (30, 15), 0, 0, 180, (100, 100, 100), 2)  # Mouth

    # Encode to JPEG
    success, buffer = cv2.imencode(".jpg", img)
    assert success
    return buffer.tobytes()


@pytest.fixture
def mock_face_detector():
    """Mock face detector that returns successful detection."""
    detector = Mock()
    detector.detect = AsyncMock(
        return_value=FaceDetectionResult(
            found=True,
            bounding_box=(50, 50, 100, 100),
            landmarks=np.array([[75, 85], [125, 85], [100, 110], [80, 130], [120, 130]]),
            confidence=0.98,
        )
    )
    return detector


@pytest.fixture
def mock_embedding_extractor():
    """Mock embedding extractor that returns consistent embeddings."""
    extractor = Mock()
    # Return same embedding for same "user" to simulate real face matching
    extractor.extract = AsyncMock(
        return_value=np.random.randn(128).astype(np.float32)
    )
    return extractor


# ============================================================================
# Enrollment → Verification Workflow Tests
# ============================================================================


class TestEnrollmentVerificationWorkflow:
    """Test complete enrollment and verification workflow."""

    def test_enroll_then_verify_same_user(
        self,
        client,
        temp_storage_dir,
        real_image,
        mock_face_detector,
        mock_embedding_extractor,
    ):
        """Test enrolling a user then verifying them successfully."""
        # Create shared repository and storage
        repository = InMemoryEmbeddingRepository()
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Create a fixed embedding for this test
        fixed_embedding = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=fixed_embedding.copy())

        # Create enrollment use case with real components
        from app.application.use_cases.enroll_face import EnrollFaceUseCase
        from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
        from app.infrastructure.ml.similarity.cosine_similarity import (
            CosineSimilarityCalculator,
        )

        quality_assessor = QualityAssessor()
        enroll_use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            quality_assessor=quality_assessor,
            extractor=mock_embedding_extractor,
            repository=repository,
        )

        # Create verification use case
        from app.application.use_cases.verify_face import VerifyFaceUseCase

        similarity_calculator = CosineSimilarityCalculator(threshold=0.6)
        verify_use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=repository,
            similarity_calculator=similarity_calculator,
        )

        # Override dependencies
        app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_use_case
        app.dependency_overrides[get_verify_face_use_case] = lambda: verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        # Step 1: Enroll user
        enroll_response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_001"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert enroll_response.status_code == 200
        enroll_data = enroll_response.json()
        assert enroll_data["success"] is True
        assert enroll_data["user_id"] == "test_user_001"
        assert enroll_data["embedding_dimension"] == 128

        # Step 2: Verify same user (should match)
        verify_response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_001"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["verified"] is True
        assert verify_data["confidence"] > 0.9  # Same embedding = high confidence
        assert verify_data["distance"] < 0.1  # Same embedding = low distance

    def test_verify_different_user_fails(
        self,
        client,
        temp_storage_dir,
        real_image,
        mock_face_detector,
        mock_embedding_extractor,
    ):
        """Test that verifying with different embedding fails."""
        repository = InMemoryEmbeddingRepository()
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.enroll_face import EnrollFaceUseCase
        from app.application.use_cases.verify_face import VerifyFaceUseCase
        from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
        from app.infrastructure.ml.similarity.cosine_similarity import (
            CosineSimilarityCalculator,
        )

        quality_assessor = QualityAssessor()
        similarity_calculator = CosineSimilarityCalculator(threshold=0.6)

        # First embedding for enrollment
        enrollment_embedding = np.random.randn(128).astype(np.float32)

        enroll_use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            quality_assessor=quality_assessor,
            extractor=mock_embedding_extractor,
            repository=repository,
        )

        verify_use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=repository,
            similarity_calculator=similarity_calculator,
        )

        app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_use_case
        app.dependency_overrides[get_verify_face_use_case] = lambda: verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        # Enroll with first embedding
        mock_embedding_extractor.extract = AsyncMock(return_value=enrollment_embedding.copy())

        enroll_response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_002"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )
        assert enroll_response.status_code == 200

        # Verify with completely different embedding (different person)
        different_embedding = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=different_embedding)

        verify_response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_002"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["verified"] is False
        assert verify_data["confidence"] < 0.5  # Different embeddings = low confidence

    def test_verify_non_enrolled_user_returns_404(
        self, client, temp_storage_dir, real_image, mock_face_detector, mock_embedding_extractor
    ):
        """Test verifying a user who hasn't enrolled returns 404."""
        repository = InMemoryEmbeddingRepository()
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.verify_face import VerifyFaceUseCase
        from app.infrastructure.ml.similarity.cosine_similarity import (
            CosineSimilarityCalculator,
        )

        similarity_calculator = CosineSimilarityCalculator(threshold=0.6)
        verify_use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=repository,
            similarity_calculator=similarity_calculator,
        )

        app.dependency_overrides[get_verify_face_use_case] = lambda: verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "non_existent_user"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert response.status_code == 404
        data = response.json()
        assert "enroll" in data["message"].lower()


# ============================================================================
# Multi-Tenant Isolation Tests
# ============================================================================


class TestMultiTenantIsolation:
    """Test that tenants are properly isolated from each other."""

    def test_same_user_id_different_tenants(
        self,
        client,
        temp_storage_dir,
        real_image,
        mock_face_detector,
        mock_embedding_extractor,
    ):
        """Test same user_id can exist in different tenants."""
        repository = InMemoryEmbeddingRepository()
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.enroll_face import EnrollFaceUseCase
        from app.application.use_cases.verify_face import VerifyFaceUseCase
        from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
        from app.infrastructure.ml.similarity.cosine_similarity import (
            CosineSimilarityCalculator,
        )

        quality_assessor = QualityAssessor()
        similarity_calculator = CosineSimilarityCalculator(threshold=0.6)

        enroll_use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            quality_assessor=quality_assessor,
            extractor=mock_embedding_extractor,
            repository=repository,
        )

        verify_use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=repository,
            similarity_calculator=similarity_calculator,
        )

        app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_use_case
        app.dependency_overrides[get_verify_face_use_case] = lambda: verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        # Enroll same user_id in tenant_a with embedding A
        embedding_a = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=embedding_a.copy())

        response_a = client.post(
            "/api/v1/enroll",
            data={"user_id": "shared_user_id", "tenant_id": "tenant_a"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )
        assert response_a.status_code == 200

        # Enroll same user_id in tenant_b with different embedding B
        embedding_b = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=embedding_b.copy())

        response_b = client.post(
            "/api/v1/enroll",
            data={"user_id": "shared_user_id", "tenant_id": "tenant_b"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )
        assert response_b.status_code == 200

        # Verify user in tenant_a with embedding A (should match)
        mock_embedding_extractor.extract = AsyncMock(return_value=embedding_a.copy())

        verify_a = client.post(
            "/api/v1/verify",
            data={"user_id": "shared_user_id", "tenant_id": "tenant_a"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_a.status_code == 200
        assert verify_a.json()["verified"] is True

        # Verify user in tenant_b with embedding B (should match)
        mock_embedding_extractor.extract = AsyncMock(return_value=embedding_b.copy())

        verify_b = client.post(
            "/api/v1/verify",
            data={"user_id": "shared_user_id", "tenant_id": "tenant_b"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_b.status_code == 200
        assert verify_b.json()["verified"] is True

    def test_tenant_isolation_prevents_cross_access(
        self,
        client,
        temp_storage_dir,
        real_image,
        mock_face_detector,
        mock_embedding_extractor,
    ):
        """Test that users from one tenant cannot verify in another."""
        repository = InMemoryEmbeddingRepository()
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.enroll_face import EnrollFaceUseCase
        from app.application.use_cases.verify_face import VerifyFaceUseCase
        from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
        from app.infrastructure.ml.similarity.cosine_similarity import (
            CosineSimilarityCalculator,
        )

        quality_assessor = QualityAssessor()
        similarity_calculator = CosineSimilarityCalculator(threshold=0.6)

        enroll_use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            quality_assessor=quality_assessor,
            extractor=mock_embedding_extractor,
            repository=repository,
        )

        verify_use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=repository,
            similarity_calculator=similarity_calculator,
        )

        app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_use_case
        app.dependency_overrides[get_verify_face_use_case] = lambda: verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        # Enroll user only in tenant_a
        embedding = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=embedding.copy())

        enroll_response = client.post(
            "/api/v1/enroll",
            data={"user_id": "isolated_user", "tenant_id": "tenant_a"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )
        assert enroll_response.status_code == 200

        # Try to verify same user in tenant_b (should fail - not found)
        verify_response = client.post(
            "/api/v1/verify",
            data={"user_id": "isolated_user", "tenant_id": "tenant_b"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_response.status_code == 404


# ============================================================================
# Liveness Check Workflow Tests
# ============================================================================


class TestLivenessWorkflow:
    """Test liveness detection workflow."""

    def test_liveness_check_pass(
        self, client, temp_storage_dir, real_image, mock_face_detector
    ):
        """Test successful liveness check."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.check_liveness import CheckLivenessUseCase
        from app.infrastructure.ml.liveness.stub_liveness_detector import (
            StubLivenessDetector,
        )

        liveness_detector = StubLivenessDetector()
        liveness_use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=liveness_detector,
        )

        app.dependency_overrides[get_check_liveness_use_case] = lambda: liveness_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        response = client.post(
            "/api/v1/liveness",
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_live"] is True
        assert data["liveness_score"] >= 70.0  # Stub returns high score


# ============================================================================
# Error Recovery Tests
# ============================================================================


class TestErrorRecovery:
    """Test system behavior under error conditions."""

    def test_enrollment_updates_existing_user(
        self,
        client,
        temp_storage_dir,
        real_image,
        mock_face_detector,
        mock_embedding_extractor,
    ):
        """Test that re-enrolling updates the user's embedding."""
        repository = InMemoryEmbeddingRepository()
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.enroll_face import EnrollFaceUseCase
        from app.application.use_cases.verify_face import VerifyFaceUseCase
        from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
        from app.infrastructure.ml.similarity.cosine_similarity import (
            CosineSimilarityCalculator,
        )

        quality_assessor = QualityAssessor()
        similarity_calculator = CosineSimilarityCalculator(threshold=0.6)

        enroll_use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            quality_assessor=quality_assessor,
            extractor=mock_embedding_extractor,
            repository=repository,
        )

        verify_use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=repository,
            similarity_calculator=similarity_calculator,
        )

        app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_use_case
        app.dependency_overrides[get_verify_face_use_case] = lambda: verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        # First enrollment
        old_embedding = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=old_embedding.copy())

        response1 = client.post(
            "/api/v1/enroll",
            data={"user_id": "update_user"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )
        assert response1.status_code == 200

        # Re-enroll with new embedding
        new_embedding = np.random.randn(128).astype(np.float32)
        mock_embedding_extractor.extract = AsyncMock(return_value=new_embedding.copy())

        response2 = client.post(
            "/api/v1/enroll",
            data={"user_id": "update_user"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )
        assert response2.status_code == 200

        # Verify with new embedding should match
        verify_response = client.post(
            "/api/v1/verify",
            data={"user_id": "update_user"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_response.status_code == 200
        assert verify_response.json()["verified"] is True

        # Verify with old embedding should NOT match
        mock_embedding_extractor.extract = AsyncMock(return_value=old_embedding.copy())

        verify_old = client.post(
            "/api/v1/verify",
            data={"user_id": "update_user"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert verify_old.status_code == 200
        assert verify_old.json()["verified"] is False

    def test_temp_files_cleaned_up_on_error(
        self, temp_storage_dir, real_image
    ):
        """Test that temporary files are cleaned up even when errors occur."""
        # Use client with raise_server_exceptions=False to get 500 response
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)

        storage = LocalFileStorage(storage_path=temp_storage_dir)

        from app.application.use_cases.enroll_face import EnrollFaceUseCase
        from app.infrastructure.ml.quality.quality_assessor import QualityAssessor

        # Mock detector to raise error
        failing_detector = Mock()
        failing_detector.detect = AsyncMock(side_effect=Exception("Detection failed"))

        quality_assessor = QualityAssessor()
        repository = InMemoryEmbeddingRepository()

        enroll_use_case = EnrollFaceUseCase(
            detector=failing_detector,
            quality_assessor=quality_assessor,
            extractor=Mock(),
            repository=repository,
        )

        app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_use_case
        app.dependency_overrides[get_file_storage] = lambda: storage

        # This should fail but cleanup temp file
        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "cleanup_test"},
            files={"file": ("face.jpg", io.BytesIO(real_image), "image/jpeg")},
        )

        assert response.status_code == 500

        # Check temp directory is empty (files were cleaned up)
        import os
        temp_files = os.listdir(temp_storage_dir)
        assert len(temp_files) == 0, f"Temp files not cleaned up: {temp_files}"

        app.dependency_overrides.clear()
