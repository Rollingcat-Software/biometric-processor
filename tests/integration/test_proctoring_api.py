"""Integration tests for proctoring API routes."""

import base64
import pytest
import sys
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient

# Mock ML dependencies before imports
sys.modules['mediapipe'] = Mock()
sys.modules['ultralytics'] = Mock()

from app.main import app
from app.api.dependencies.proctor import (
    get_proctor_session_repository,
    get_proctor_incident_repository,
    get_session_rate_limiter,
    get_gaze_tracker,
    get_object_detector,
    get_deepfake_detector,
    get_audio_analyzer,
    clear_proctor_cache,
)
from app.domain.entities.proctor_session import ProctorSession, SessionStatus
from app.domain.entities.proctor_incident import ProctorIncident, IncidentType, IncidentSeverity


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create test client."""
    app.dependency_overrides.clear()
    clear_proctor_cache()

    yield TestClient(app)

    app.dependency_overrides.clear()
    clear_proctor_cache()


@pytest.fixture
def tenant_headers():
    """Headers with tenant ID."""
    return {"X-Tenant-ID": "test-tenant-001"}


@pytest.fixture
def reviewer_headers(tenant_headers):
    """Headers with tenant and reviewer ID."""
    return {**tenant_headers, "X-Reviewer-ID": "reviewer-001"}


@pytest.fixture
def sample_frame_base64():
    """Generate a valid test frame (gray image)."""
    import cv2

    # Create a simple test image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (100, 100, 100)  # Gray background

    # Add a simple "face-like" region
    cv2.rectangle(img, (250, 150), (390, 330), (200, 180, 160), -1)

    # Encode to base64
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')


@pytest.fixture
def mock_session_repository():
    """Create mock session repository."""
    repo = Mock()

    # Storage for sessions
    sessions = {}

    async def save(session):
        sessions[session.id] = session

    async def get_by_id(session_id, tenant_id):
        session = sessions.get(session_id)
        if session and session.tenant_id == tenant_id:
            return session
        return None

    async def get_active_sessions(tenant_id, limit=100, offset=0):
        return [s for s in sessions.values()
                if s.tenant_id == tenant_id and s.status in [SessionStatus.ACTIVE, SessionStatus.FLAGGED]]

    async def get_sessions_by_exam(exam_id, tenant_id, limit=100, offset=0):
        return [s for s in sessions.values()
                if s.exam_id == exam_id and s.tenant_id == tenant_id]

    async def get_sessions_by_user(user_id, tenant_id, limit=100, offset=0):
        return [s for s in sessions.values()
                if s.user_id == user_id and s.tenant_id == tenant_id]

    async def get_sessions_by_status(status, tenant_id, limit=100, offset=0):
        return [s for s in sessions.values()
                if s.status == status and s.tenant_id == tenant_id]

    repo.save = AsyncMock(side_effect=save)
    repo.get_by_id = AsyncMock(side_effect=get_by_id)
    repo.get_active_sessions = AsyncMock(side_effect=get_active_sessions)
    repo.get_sessions_by_exam = AsyncMock(side_effect=get_sessions_by_exam)
    repo.get_sessions_by_user = AsyncMock(side_effect=get_sessions_by_user)
    repo.get_sessions_by_status = AsyncMock(side_effect=get_sessions_by_status)
    repo._sessions = sessions

    return repo


@pytest.fixture
def mock_incident_repository():
    """Create mock incident repository."""
    repo = Mock()

    incidents = {}

    async def save(incident):
        incidents[incident.id] = incident

    async def get_by_id(incident_id):
        return incidents.get(incident_id)

    async def get_by_session(session_id, limit=100, offset=0):
        return [i for i in incidents.values() if i.session_id == session_id]

    repo.save = AsyncMock(side_effect=save)
    repo.get_by_id = AsyncMock(side_effect=get_by_id)
    repo.get_by_session = AsyncMock(side_effect=get_by_session)
    repo.count_by_session = AsyncMock(return_value=0)
    repo._incidents = incidents

    return repo


@pytest.fixture
def mock_rate_limiter():
    """Create mock rate limiter."""
    limiter = Mock()
    limiter.check = AsyncMock(return_value={
        "allowed": True,
        "remaining": 100,
        "reset_at": None,
    })
    limiter.get_session_stats = AsyncMock(return_value={
        "frames_last_minute": 5,
        "remaining_this_minute": 115,
        "violation_count": 0,
        "is_throttled": False,
    })
    return limiter


@pytest.fixture
def mock_ml_components():
    """Create mock ML components that return None (disabled)."""
    return {
        "gaze_tracker": None,
        "object_detector": None,
        "deepfake_detector": None,
        "audio_analyzer": None,
    }


@pytest.fixture
def setup_mocks(client, mock_session_repository, mock_incident_repository, mock_rate_limiter, mock_ml_components):
    """Set up dependency overrides with mocks."""
    app.dependency_overrides[get_proctor_session_repository] = lambda: mock_session_repository
    app.dependency_overrides[get_proctor_incident_repository] = lambda: mock_incident_repository
    app.dependency_overrides[get_session_rate_limiter] = lambda: mock_rate_limiter
    app.dependency_overrides[get_gaze_tracker] = lambda: mock_ml_components["gaze_tracker"]
    app.dependency_overrides[get_object_detector] = lambda: mock_ml_components["object_detector"]
    app.dependency_overrides[get_deepfake_detector] = lambda: mock_ml_components["deepfake_detector"]
    app.dependency_overrides[get_audio_analyzer] = lambda: mock_ml_components["audio_analyzer"]

    return {
        "session_repo": mock_session_repository,
        "incident_repo": mock_incident_repository,
        "rate_limiter": mock_rate_limiter,
    }


# ============================================================================
# Session Lifecycle Tests
# ============================================================================


class TestSessionLifecycle:
    """Integration tests for session lifecycle."""

    def test_create_session(self, client, tenant_headers, setup_mocks):
        """Test creating a new proctoring session."""
        response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={
                "exam_id": "exam-001",
                "user_id": "user-001",
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["exam_id"] == "exam-001"
        assert data["user_id"] == "user-001"
        assert data["status"] == "created"

    def test_create_session_with_config(self, client, tenant_headers, setup_mocks):
        """Test creating a session with custom configuration."""
        response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={
                "exam_id": "exam-002",
                "user_id": "user-002",
                "config": {
                    "verification_interval_sec": 30,
                    "risk_threshold_warning": 0.6,
                }
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data

    def test_create_session_missing_tenant(self, client, setup_mocks):
        """Test creating session without tenant ID fails."""
        response = client.post(
            "/api/v1/proctoring/sessions",
            json={
                "exam_id": "exam-001",
                "user_id": "user-001",
            }
        )

        assert response.status_code == 422  # Missing required header

    def test_get_session(self, client, tenant_headers, setup_mocks):
        """Test getting session details."""
        # First create a session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={
                "exam_id": "exam-001",
                "user_id": "user-001",
            }
        )
        session_id = create_response.json()["session_id"]

        # Get the session
        response = client.get(
            f"/api/v1/proctoring/sessions/{session_id}",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exam_id"] == "exam-001"

    def test_get_session_not_found(self, client, tenant_headers, setup_mocks):
        """Test getting non-existent session."""
        fake_id = str(uuid4())

        response = client.get(
            f"/api/v1/proctoring/sessions/{fake_id}",
            headers=tenant_headers,
        )

        assert response.status_code == 404

    def test_list_sessions(self, client, tenant_headers, setup_mocks):
        """Test listing sessions."""
        # Create a few sessions
        for i in range(3):
            client.post(
                "/api/v1/proctoring/sessions",
                headers=tenant_headers,
                json={
                    "exam_id": f"exam-{i}",
                    "user_id": f"user-{i}",
                }
            )

        # List sessions
        response = client.get(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data

    def test_list_sessions_by_exam(self, client, tenant_headers, setup_mocks):
        """Test listing sessions filtered by exam."""
        # Create sessions for different exams
        client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-A", "user_id": "user-1"}
        )
        client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-B", "user_id": "user-2"}
        )

        # Filter by exam
        response = client.get(
            "/api/v1/proctoring/sessions?exam_id=exam-A",
            headers=tenant_headers,
        )

        assert response.status_code == 200


class TestSessionStateTransitions:
    """Tests for session state transitions."""

    def test_start_session(self, client, tenant_headers, setup_mocks):
        """Test starting a session."""
        # Create session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        # Start session
        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    def test_pause_session(self, client, tenant_headers, setup_mocks):
        """Test pausing a session."""
        # Create and start session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        # Pause
        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/pause",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_resume_session(self, client, tenant_headers, setup_mocks):
        """Test resuming a paused session."""
        # Create, start, and pause session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        client.post(f"/api/v1/proctoring/sessions/{session_id}/start", headers=tenant_headers)
        client.post(f"/api/v1/proctoring/sessions/{session_id}/pause", headers=tenant_headers)

        # Resume
        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/resume",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_end_session(self, client, tenant_headers, setup_mocks):
        """Test ending a session."""
        # Create and start session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        client.post(f"/api/v1/proctoring/sessions/{session_id}/start", headers=tenant_headers)

        # End
        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/end",
            headers=tenant_headers,
            json={"reason": "completed"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "duration_seconds" in data


# ============================================================================
# Incident Tests
# ============================================================================


class TestIncidentManagement:
    """Tests for incident management."""

    def test_create_incident(self, client, tenant_headers, setup_mocks):
        """Test creating an incident manually."""
        # Create and start session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]
        client.post(f"/api/v1/proctoring/sessions/{session_id}/start", headers=tenant_headers)

        # Create incident
        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
            json={
                "incident_type": "FACE_NOT_DETECTED",
                "confidence": 0.95,
                "details": {"reason": "User looked away"}
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "incident_id" in data
        assert data["incident_type"] == "FACE_NOT_DETECTED"

    def test_list_incidents(self, client, tenant_headers, setup_mocks):
        """Test listing incidents for a session."""
        # Create session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        # List incidents
        response = client.get(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        assert "total" in data

    def test_get_incident(self, client, tenant_headers, setup_mocks):
        """Test getting incident details."""
        # Create session and incident
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]
        client.post(f"/api/v1/proctoring/sessions/{session_id}/start", headers=tenant_headers)

        incident_response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
            json={"incident_type": "FACE_NOT_DETECTED", "confidence": 0.9}
        )
        incident_id = incident_response.json()["incident_id"]

        # Get incident
        response = client.get(f"/api/v1/proctoring/incidents/{incident_id}")

        assert response.status_code == 200

    def test_review_incident(self, client, reviewer_headers, setup_mocks):
        """Test reviewing an incident."""
        # Create session and incident
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers={"X-Tenant-ID": "test-tenant-001"},
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]
        client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers={"X-Tenant-ID": "test-tenant-001"}
        )

        incident_response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers={"X-Tenant-ID": "test-tenant-001"},
            json={"incident_type": "FACE_NOT_DETECTED", "confidence": 0.9}
        )
        incident_id = incident_response.json()["incident_id"]

        # Review
        response = client.post(
            f"/api/v1/proctoring/incidents/{incident_id}/review",
            headers=reviewer_headers,
            json={
                "action": "DISMISSED",
                "notes": "False positive - user sneezed"
            }
        )

        assert response.status_code == 200

    def test_review_incident_without_reviewer(self, client, tenant_headers, setup_mocks):
        """Test reviewing incident without reviewer ID fails."""
        fake_incident_id = str(uuid4())

        response = client.post(
            f"/api/v1/proctoring/incidents/{fake_incident_id}/review",
            headers=tenant_headers,  # Missing X-Reviewer-ID
            json={"action": "DISMISSED"}
        )

        assert response.status_code == 400


# ============================================================================
# Report Tests
# ============================================================================


class TestReports:
    """Tests for session reports."""

    def test_get_session_report(self, client, tenant_headers, setup_mocks):
        """Test getting session report."""
        # Create and start session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]
        client.post(f"/api/v1/proctoring/sessions/{session_id}/start", headers=tenant_headers)

        # Get report
        response = client.get(
            f"/api/v1/proctoring/sessions/{session_id}/report",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "risk_score" in data


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_get_rate_limit_status(self, client, setup_mocks):
        """Test getting rate limit status."""
        session_id = str(uuid4())

        response = client.get(
            f"/api/v1/proctoring/sessions/{session_id}/rate-limit"
        )

        assert response.status_code == 200
        data = response.json()
        assert "frames_last_minute" in data
        assert "remaining_this_minute" in data


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_uuid_format(self, client, tenant_headers, setup_mocks):
        """Test invalid UUID format."""
        response = client.get(
            "/api/v1/proctoring/sessions/not-a-uuid",
            headers=tenant_headers,
        )

        assert response.status_code == 422

    def test_invalid_incident_type(self, client, tenant_headers, setup_mocks):
        """Test invalid incident type."""
        # Create session
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        # Try to create invalid incident
        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
            json={"incident_type": "INVALID_TYPE", "confidence": 0.9}
        )

        assert response.status_code in [400, 422]

    def test_invalid_confidence_value(self, client, tenant_headers, setup_mocks):
        """Test invalid confidence value (out of range)."""
        create_response = client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={"exam_id": "exam-001", "user_id": "user-001"}
        )
        session_id = create_response.json()["session_id"]

        response = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
            json={"incident_type": "FACE_NOT_DETECTED", "confidence": 1.5}  # Invalid
        )

        assert response.status_code in [400, 422]
