"""Integration tests for API routes."""

import pytest
import io
import sys
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
import numpy as np
import cv2

# Mock DeepFace before any imports that depend on it
sys.modules['deepface'] = Mock()
sys.modules['deepface.DeepFace'] = Mock()

from app.main import app
from app.core.container import (
    get_enroll_face_use_case,
    get_verify_face_use_case,
    get_check_liveness_use_case,
    get_file_storage,
)
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.verification_result import VerificationResult
from app.domain.entities.liveness_result import LivenessResult
from app.domain.exceptions.face_errors import (
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
)
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError
from datetime import datetime


@pytest.fixture
def client():
    """Create test client."""
    # Clear any existing overrides
    app.dependency_overrides.clear()

    yield TestClient(app)

    # Clean up after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_enroll_use_case():
    """Create mock enrollment use case."""
    use_case = Mock()

    # Create mock result
    embedding = FaceEmbedding.create_new(
        user_id="test_user",
        vector=np.random.randn(128).astype(np.float32),
        quality_score=85.0,
    )

    use_case.execute = AsyncMock(return_value=embedding)
    return use_case


@pytest.fixture
def mock_verify_use_case():
    """Create mock verification use case."""
    use_case = Mock()

    # Create mock result (successful match)
    result = VerificationResult(
        verified=True,
        confidence=0.87,
        distance=0.13,
        threshold=0.6,
    )

    use_case.execute = AsyncMock(return_value=result)
    return use_case


@pytest.fixture
def mock_liveness_use_case():
    """Create mock liveness check use case."""
    use_case = Mock()

    # Create mock result (liveness passed)
    result = LivenessResult(
        is_live=True,
        liveness_score=92.0,
        challenge="none",
        challenge_completed=True,
    )

    use_case.execute = AsyncMock(return_value=result)
    return use_case


@pytest.fixture
def mock_file_storage():
    """Create mock file storage."""
    storage = Mock()
    storage.save_temp = AsyncMock(return_value="/tmp/test_image.jpg")
    storage.cleanup = AsyncMock()
    return storage


@pytest.fixture
def test_image_file():
    """Create test image file."""
    # Create a small valid image (100x100 black image)
    img = np.zeros((100, 100, 3), dtype=np.uint8)

    # Encode to JPEG
    success, buffer = cv2.imencode('.jpg', img)
    assert success, "Failed to encode test image"

    image_bytes = buffer.tobytes()
    return ("test.jpg", io.BytesIO(image_bytes), "image/jpeg")


# ============================================================================
# Health Check Endpoint Tests
# ============================================================================


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_success(self, client):
        """Test health check returns 200."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data
        assert "model" in data
        assert "detector" in data

    def test_health_check_response_structure(self, client):
        """Test health check response has correct structure."""
        response = client.get("/api/v1/health")

        data = response.json()

        # Verify all required fields
        assert "status" in data
        assert "version" in data
        assert "model" in data
        assert "detector" in data


# ============================================================================
# Enrollment Endpoint Tests
# ============================================================================


class TestEnrollmentEndpoint:
    """Test enrollment endpoint."""

    def test_enroll_success(
        self, client, mock_enroll_use_case, mock_file_storage, test_image_file
    ):
        """Test successful face enrollment."""
        # Override dependencies
        app.dependency_overrides[get_enroll_face_use_case] = lambda: mock_enroll_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["user_id"] == "test_user"
        assert data["quality_score"] == 85.0
        assert "message" in data
        assert data["embedding_dimension"] == 128

    def test_enroll_with_tenant_id(
        self, client, mock_enroll_use_case, mock_file_storage, test_image_file
    ):
        """Test enrollment with tenant ID."""
        # Override dependencies
        app.dependency_overrides[get_enroll_face_use_case] = lambda: mock_enroll_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_123", "tenant_id": "tenant_xyz"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200

        # Verify use case was called with tenant_id
        mock_enroll_use_case.execute.assert_called_once()
        call_kwargs = mock_enroll_use_case.execute.call_args.kwargs
        assert call_kwargs["tenant_id"] == "tenant_xyz"

    def test_enroll_invalid_file_type(self, client):
        """Test enrollment rejects non-image files."""
        text_file = ("test.txt", io.BytesIO(b"not an image"), "text/plain")

        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_123"},
            files={"file": text_file},
        )

        assert response.status_code == 400
        data = response.json()
        # HTTPException uses "detail" field
        assert "image" in data["detail"].lower()

    def test_enroll_no_face_detected(
        self, client, mock_enroll_use_case, mock_file_storage, test_image_file
    ):
        """Test enrollment fails when no face detected."""
        # Override dependencies
        app.dependency_overrides[get_enroll_face_use_case] = lambda: mock_enroll_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        # Configure use case to raise FaceNotDetectedError
        mock_enroll_use_case.execute = AsyncMock(
            side_effect=FaceNotDetectedError()
        )

        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 400
        data = response.json()
        assert "face" in data["message"].lower()

    def test_enroll_poor_quality(
        self, client, mock_enroll_use_case, mock_file_storage, test_image_file
    ):
        """Test enrollment fails with poor image quality."""
        # Override dependencies
        app.dependency_overrides[get_enroll_face_use_case] = lambda: mock_enroll_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        # Configure use case to raise PoorImageQualityError
        mock_enroll_use_case.execute = AsyncMock(
            side_effect=PoorImageQualityError(
                quality_score=35.0, min_threshold=70.0
            )
        )

        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 400
        data = response.json()
        assert "quality" in data["message"].lower()

    def test_enroll_cleanup_called(
        self, client, mock_enroll_use_case, mock_file_storage, test_image_file
    ):
        """Test that file cleanup is always called."""
        # Override dependencies
        app.dependency_overrides[get_enroll_face_use_case] = lambda: mock_enroll_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200

        # Verify cleanup was called
        mock_file_storage.cleanup.assert_called_once()
        cleanup_path = mock_file_storage.cleanup.call_args.args[0]
        assert cleanup_path == "/tmp/test_image.jpg"


# ============================================================================
# Verification Endpoint Tests
# ============================================================================


class TestVerificationEndpoint:
    """Test verification endpoint."""

    def test_verify_success_match(
        self, client, mock_verify_use_case, mock_file_storage, test_image_file
    ):
        """Test successful verification with match."""
        # Override dependencies
        app.dependency_overrides[get_verify_face_use_case] = lambda: mock_verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["verified"] is True
        assert data["confidence"] == 0.87
        assert data["distance"] == 0.13
        assert data["threshold"] == 0.6
        assert "verified" in data["message"].lower() or "match" in data["message"].lower()

    def test_verify_success_no_match(
        self, client, mock_verify_use_case, mock_file_storage, test_image_file
    ):
        """Test successful verification with no match."""
        # Override dependencies
        app.dependency_overrides[get_verify_face_use_case] = lambda: mock_verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        # Configure use case to return no match
        result = VerificationResult(
            verified=False,
            confidence=0.32,
            distance=0.68,
            threshold=0.6,
        )
        mock_verify_use_case.execute = AsyncMock(return_value=result)

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["verified"] is False
        assert data["confidence"] == 0.32

    def test_verify_user_not_enrolled(
        self, client, mock_verify_use_case, mock_file_storage, test_image_file
    ):
        """Test verification fails when user not enrolled."""
        # Override dependencies
        app.dependency_overrides[get_verify_face_use_case] = lambda: mock_verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        # Configure use case to raise EmbeddingNotFoundError
        mock_verify_use_case.execute = AsyncMock(
            side_effect=EmbeddingNotFoundError(user_id="unknown_user")
        )

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "unknown_user"},
            files={"file": test_image_file},
        )

        assert response.status_code == 404
        data = response.json()
        assert "enroll" in data["message"].lower()

    def test_verify_invalid_file_type(self, client):
        """Test verification rejects non-image files."""
        text_file = ("test.txt", io.BytesIO(b"not an image"), "text/plain")

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": text_file},
        )

        assert response.status_code == 400
        data = response.json()
        # HTTPException uses "detail" field
        assert "image" in data["detail"].lower()

    def test_verify_with_tenant_id(
        self, client, mock_verify_use_case, mock_file_storage, test_image_file
    ):
        """Test verification with tenant ID."""
        # Override dependencies
        app.dependency_overrides[get_verify_face_use_case] = lambda: mock_verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123", "tenant_id": "tenant_xyz"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200

        # Verify use case was called with tenant_id
        mock_verify_use_case.execute.assert_called_once()
        call_kwargs = mock_verify_use_case.execute.call_args.kwargs
        assert call_kwargs["tenant_id"] == "tenant_xyz"

    def test_verify_cleanup_called(
        self, client, mock_verify_use_case, mock_file_storage, test_image_file
    ):
        """Test that file cleanup is always called."""
        # Override dependencies
        app.dependency_overrides[get_verify_face_use_case] = lambda: mock_verify_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

        assert response.status_code == 200

        # Verify cleanup was called
        mock_file_storage.cleanup.assert_called_once()
        cleanup_path = mock_file_storage.cleanup.call_args.args[0]
        assert cleanup_path == "/tmp/test_image.jpg"


# ============================================================================
# Liveness Check Endpoint Tests
# ============================================================================


class TestLivenessEndpoint:
    """Test liveness check endpoint."""

    def test_liveness_success_pass(
        self, client, mock_liveness_use_case, mock_file_storage, test_image_file
    ):
        """Test successful liveness check (passed)."""
        # Override dependencies
        app.dependency_overrides[get_check_liveness_use_case] = lambda: mock_liveness_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/liveness",
            files={"file": test_image_file},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_live"] is True
        assert data["liveness_score"] == 92.0
        assert data["challenge"] == "none"
        assert data["challenge_completed"] is True

    def test_liveness_success_fail(
        self, client, mock_liveness_use_case, mock_file_storage, test_image_file
    ):
        """Test successful liveness check (failed)."""
        # Override dependencies
        app.dependency_overrides[get_check_liveness_use_case] = lambda: mock_liveness_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        # Configure use case to return liveness failed
        result = LivenessResult(
            is_live=False,
            liveness_score=35.0,
            challenge="none",
            challenge_completed=True,
        )
        mock_liveness_use_case.execute = AsyncMock(return_value=result)

        response = client.post(
            "/api/v1/liveness",
            files={"file": test_image_file},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_live"] is False
        assert data["liveness_score"] == 35.0

    def test_liveness_invalid_file_type(self, client):
        """Test liveness check rejects non-image files."""
        text_file = ("test.txt", io.BytesIO(b"not an image"), "text/plain")

        response = client.post(
            "/api/v1/liveness",
            files={"file": text_file},
        )

        assert response.status_code == 400
        data = response.json()
        # HTTPException uses "detail" field
        assert "image" in data["detail"].lower()

    def test_liveness_no_face_detected(
        self, client, mock_liveness_use_case, mock_file_storage, test_image_file
    ):
        """Test liveness check fails when no face detected."""
        # Override dependencies
        app.dependency_overrides[get_check_liveness_use_case] = lambda: mock_liveness_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        # Configure use case to raise FaceNotDetectedError
        mock_liveness_use_case.execute = AsyncMock(
            side_effect=FaceNotDetectedError()
        )

        response = client.post(
            "/api/v1/liveness",
            files={"file": test_image_file},
        )

        assert response.status_code == 400
        data = response.json()
        assert "face" in data["message"].lower()

    def test_liveness_cleanup_called(
        self, client, mock_liveness_use_case, mock_file_storage, test_image_file
    ):
        """Test that file cleanup is always called."""
        # Override dependencies
        app.dependency_overrides[get_check_liveness_use_case] = lambda: mock_liveness_use_case
        app.dependency_overrides[get_file_storage] = lambda: mock_file_storage

        response = client.post(
            "/api/v1/liveness",
            files={"file": test_image_file},
        )

        assert response.status_code == 200

        # Verify cleanup was called
        mock_file_storage.cleanup.assert_called_once()
        cleanup_path = mock_file_storage.cleanup.call_args.args[0]
        assert cleanup_path == "/tmp/test_image.jpg"
