"""Integration tests for new API routes."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import numpy as np
from io import BytesIO
from PIL import Image

from fastapi.testclient import TestClient


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_image_bytes():
    """Create test image bytes."""
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def mock_container():
    """Mock the container dependencies."""
    with patch("app.api.routes.quality.get_analyze_quality_use_case") as mock_quality, \
         patch("app.api.routes.multi_face.get_detect_multi_face_use_case") as mock_multi, \
         patch("app.api.routes.demographics.get_analyze_demographics_use_case") as mock_demo, \
         patch("app.api.routes.landmarks.get_detect_landmarks_use_case") as mock_land, \
         patch("app.api.routes.comparison.get_compare_faces_use_case") as mock_compare, \
         patch("app.api.routes.similarity_matrix.get_compute_similarity_matrix_use_case") as mock_sim, \
         patch("app.api.routes.embeddings_io.get_export_embeddings_use_case") as mock_export, \
         patch("app.api.routes.embeddings_io.get_import_embeddings_use_case") as mock_import, \
         patch("app.api.routes.webhooks.get_send_webhook_use_case") as mock_webhook:

        yield {
            "quality": mock_quality,
            "multi_face": mock_multi,
            "demographics": mock_demo,
            "landmarks": mock_land,
            "compare": mock_compare,
            "similarity": mock_sim,
            "export": mock_export,
            "import": mock_import,
            "webhook": mock_webhook,
        }


# ============================================================================
# Quality Endpoint Tests
# ============================================================================


class TestQualityEndpoint:
    """Test /api/v1/quality/analyze endpoint."""

    def test_quality_analyze_success(self, test_image_bytes, mock_container):
        """Test successful quality analysis."""
        from app.domain.entities.quality_feedback import QualityFeedback, QualityMetrics

        # Setup mock
        mock_result = QualityFeedback(
            overall_score=85.0,
            is_acceptable=True,
            metrics=QualityMetrics(
                blur_score=150.0,
                brightness_score=120.0,
                face_size_score=100.0,
            ),
            issues=[],
            recommendations=[],
        )

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["quality"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/quality/analyze",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "overall_score" in data
        assert data["is_acceptable"] is True


# ============================================================================
# Comparison Endpoint Tests
# ============================================================================


class TestComparisonEndpoint:
    """Test /api/v1/compare endpoint."""

    def test_compare_faces_success(self, test_image_bytes, mock_container):
        """Test successful face comparison."""
        from app.domain.entities.face_comparison import FaceComparisonResult, FaceInfo

        mock_result = FaceComparisonResult(
            is_match=True,
            similarity=0.87,
            distance=0.13,
            threshold=0.6,
            face1=FaceInfo(
                bounding_box=(50, 50, 100, 100),
                confidence=0.95,
            ),
            face2=FaceInfo(
                bounding_box=(50, 50, 100, 100),
                confidence=0.93,
            ),
        )

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["compare"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/compare",
            files=[
                ("file1", ("test1.jpg", test_image_bytes, "image/jpeg")),
                ("file2", ("test2.jpg", test_image_bytes, "image/jpeg")),
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert "is_match" in data
        assert "similarity" in data


# ============================================================================
# Demographics Endpoint Tests
# ============================================================================


class TestDemographicsEndpoint:
    """Test /api/v1/demographics/analyze endpoint."""

    def test_demographics_analyze_success(self, test_image_bytes, mock_container):
        """Test successful demographics analysis."""
        from app.domain.entities.demographics import (
            DemographicsResult, AgeEstimate, GenderEstimate
        )

        mock_result = DemographicsResult(
            age=AgeEstimate(value=30, confidence=0.9, range_low=25, range_high=35),
            gender=GenderEstimate(value="male", confidence=0.95),
            emotion=None,
            race=None,
        )

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["demographics"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/demographics/analyze",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "age" in data
        assert "gender" in data


# ============================================================================
# Landmarks Endpoint Tests
# ============================================================================


class TestLandmarksEndpoint:
    """Test /api/v1/landmarks/detect endpoint."""

    def test_landmarks_detect_success(self, test_image_bytes, mock_container):
        """Test successful landmark detection."""
        from app.domain.entities.face_landmarks import LandmarkResult, Landmark

        mock_result = LandmarkResult(
            landmarks=[
                Landmark(index=0, name="nose_tip", x=100.0, y=100.0, z=0.0),
                Landmark(index=1, name="left_eye", x=80.0, y=90.0, z=0.0),
            ],
            head_pose=None,
            model="mediapipe_468",
        )

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["landmarks"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/landmarks/detect",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "landmarks" in data
        assert len(data["landmarks"]) > 0


# ============================================================================
# Embeddings Export/Import Endpoint Tests
# ============================================================================


class TestEmbeddingsIOEndpoint:
    """Test /api/v1/embeddings/export and /api/v1/embeddings/import endpoints."""

    def test_export_embeddings_success(self, mock_container):
        """Test successful embeddings export."""
        mock_result = {
            "embeddings": [
                {"user_id": "user1", "vector": [0.1] * 128, "quality_score": 85.0},
            ],
            "metadata": {
                "count": 1,
                "tenant_id": "default",
                "export_timestamp": "2024-01-01T00:00:00Z",
            },
        }

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["export"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.get("/api/v1/embeddings/export")

        assert response.status_code == 200
        data = response.json()
        assert "embeddings" in data
        assert "metadata" in data

    def test_import_embeddings_success(self, mock_container):
        """Test successful embeddings import."""
        mock_result = {
            "imported": 5,
            "skipped": 1,
            "errors": [],
        }

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["import"].return_value = mock_use_case

        import_data = {
            "embeddings": [
                {"user_id": "user1", "vector": [0.1] * 128, "quality_score": 85.0},
            ],
            "metadata": {"count": 1},
        }

        from app.main import app
        client = TestClient(app)

        import json
        response = client.post(
            "/api/v1/embeddings/import",
            files={"file": ("export.json", json.dumps(import_data), "application/json")},
            data={"mode": "merge", "tenant_id": "default"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "imported" in data


# ============================================================================
# Webhooks Endpoint Tests
# ============================================================================


class TestWebhooksEndpoint:
    """Test /api/v1/webhooks endpoints."""

    def test_register_webhook_success(self):
        """Test successful webhook registration."""
        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/webhooks/register",
            json={
                "url": "https://example.com/webhook",
                "events": ["enrollment", "verification"],
                "secret": "my_secret",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "webhook_id" in data
        assert data["url"] == "https://example.com/webhook"
        assert data["enabled"] is True

    def test_list_webhooks(self):
        """Test listing webhooks."""
        from app.main import app
        client = TestClient(app)

        # First register a webhook
        client.post(
            "/api/v1/webhooks/register",
            json={
                "url": "https://example.com/webhook",
                "events": ["enrollment"],
            },
        )

        response = client.get("/api/v1/webhooks")

        assert response.status_code == 200
        data = response.json()
        assert "webhooks" in data
        assert "count" in data

    def test_delete_webhook_success(self):
        """Test successful webhook deletion."""
        from app.main import app
        client = TestClient(app)

        # First register a webhook
        reg_response = client.post(
            "/api/v1/webhooks/register",
            json={
                "url": "https://example.com/webhook",
                "events": ["enrollment"],
            },
        )
        webhook_id = reg_response.json()["webhook_id"]

        # Delete the webhook
        response = client.delete(f"/api/v1/webhooks/{webhook_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["webhook_id"] == webhook_id

    def test_delete_webhook_not_found(self):
        """Test deleting non-existent webhook."""
        from app.main import app
        client = TestClient(app)

        response = client.delete("/api/v1/webhooks/nonexistent_id")

        assert response.status_code == 404


# ============================================================================
# Similarity Matrix Endpoint Tests
# ============================================================================


class TestSimilarityMatrixEndpoint:
    """Test /api/v1/similarity/matrix endpoint."""

    def test_similarity_matrix_success(self, test_image_bytes, mock_container):
        """Test successful similarity matrix computation."""
        from app.domain.entities.similarity_matrix import SimilarityMatrixResult, Cluster

        mock_result = SimilarityMatrixResult(
            matrix=[[1.0, 0.8], [0.8, 1.0]],
            labels=["img1", "img2"],
            clusters=[Cluster(id=0, members=[0, 1], avg_similarity=0.9)],
            threshold=0.6,
        )

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["similarity"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/similarity/matrix",
            files=[
                ("files", ("test1.jpg", test_image_bytes, "image/jpeg")),
                ("files", ("test2.jpg", test_image_bytes, "image/jpeg")),
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert "matrix" in data


# ============================================================================
# Multi-Face Detection Endpoint Tests
# ============================================================================


class TestMultiFaceEndpoint:
    """Test /api/v1/faces/detect-all endpoint."""

    def test_multi_face_detect_success(self, test_image_bytes, mock_container):
        """Test successful multi-face detection."""
        from app.domain.entities.multi_face_result import (
            MultiFaceResult, DetectedFace, BoundingBox
        )

        mock_result = MultiFaceResult(
            faces=[
                DetectedFace(
                    face_id=0,
                    bounding_box=BoundingBox(x=50, y=50, width=100, height=100),
                    confidence=0.95,
                    quality_score=85.0,
                ),
            ],
            face_count=1,
            processing_time_ms=150.0,
        )

        mock_use_case = Mock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_container["multi_face"].return_value = mock_use_case

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/faces/detect-all",
            files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "faces" in data
        assert "face_count" in data
