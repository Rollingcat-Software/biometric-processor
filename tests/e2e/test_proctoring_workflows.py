"""End-to-end tests for proctoring service workflows."""

import base64
import io
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np
from PIL import Image

# Try to import test client
try:
    from fastapi.testclient import TestClient
    from httpx import AsyncClient
except ImportError:
    TestClient = None
    AsyncClient = None


def create_test_image(width: int = 640, height: int = 480) -> str:
    """Create a test image and return as base64."""
    # Create a simple RGB image
    img_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)

    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode("utf-8")


@pytest.fixture
def test_image_base64():
    """Fixture providing a test image as base64."""
    return create_test_image()


@pytest.fixture
def tenant_headers():
    """Fixture providing standard headers."""
    return {"X-Tenant-ID": "test-tenant-e2e"}


@pytest.fixture
def mock_repositories():
    """Create mock repositories."""
    from app.infrastructure.persistence.repositories.memory_proctor_repository import (
        InMemoryProctorSessionRepository,
        InMemoryProctorIncidentRepository,
    )

    session_repo = InMemoryProctorSessionRepository()
    incident_repo = InMemoryProctorIncidentRepository()

    return session_repo, incident_repo


class TestProctorSessionWorkflow:
    """Test complete proctoring session workflows."""

    @pytest.fixture
    def mock_ml_components(self):
        """Create mock ML components."""
        gaze_tracker = MagicMock()
        gaze_tracker.analyze.return_value = {
            "on_screen": True,
            "confidence": 0.95,
            "gaze_direction": (0.0, 0.0),
        }

        object_detector = MagicMock()
        object_detector.detect.return_value = []

        deepfake_detector = MagicMock()
        deepfake_detector.analyze.return_value = {
            "is_fake": False,
            "confidence": 0.02,
        }

        return gaze_tracker, object_detector, deepfake_detector

    def test_session_entity_workflow(self, mock_repositories):
        """Test session entity state machine workflow."""
        from app.domain.entities.proctor_session import ProctorSession, SessionStatus

        # Create session
        session = ProctorSession.create(
            exam_id="e2e-exam-001",
            user_id="e2e-user-001",
            tenant_id="test-tenant",
        )

        assert session.status == SessionStatus.CREATED
        assert session.risk_score == 0.0

        # Start session
        session.start(baseline_embedding=np.random.randn(512).astype(np.float32))
        assert session.status == SessionStatus.ACTIVE
        assert session.baseline_embedding is not None

        # Pause session
        session.pause()
        assert session.status == SessionStatus.PAUSED

        # Resume session
        session.resume()
        assert session.status == SessionStatus.ACTIVE

        # Update risk score
        session.update_risk_score(0.3)
        assert session.risk_score == 0.3

        # Flag session for high risk
        session.flag()
        assert session.status == SessionStatus.FLAGGED

        # End session
        session.complete()
        assert session.status == SessionStatus.COMPLETED

    def test_incident_entity_workflow(self):
        """Test incident entity workflow."""
        from app.domain.entities.proctor_incident import (
            ProctorIncident,
            IncidentType,
            IncidentSeverity,
            ReviewAction,
        )

        session_id = uuid4()

        # Create incident
        incident = ProctorIncident.create(
            session_id=session_id,
            incident_type=IncidentType.GAZE_AWAY_PROLONGED,
            confidence=0.85,
            severity=IncidentSeverity.LOW,
            details={"duration_seconds": 3.5},
        )

        assert incident.session_id == session_id
        assert incident.incident_type == IncidentType.GAZE_AWAY_PROLONGED
        assert incident.reviewed is False

        # Review incident
        incident.mark_reviewed(
            reviewer="proctor-001",
            action=ReviewAction.DISMISSED,
            notes="Brief glance away, acceptable",
        )

        assert incident.reviewed is True
        assert incident.reviewed_by == "proctor-001"
        assert incident.review_action == ReviewAction.DISMISSED

    @pytest.mark.asyncio
    async def test_repository_workflow(self, mock_repositories):
        """Test repository save and retrieve workflow."""
        session_repo, incident_repo = mock_repositories

        from app.domain.entities.proctor_session import ProctorSession
        from app.domain.entities.proctor_incident import (
            ProctorIncident,
            IncidentType,
            IncidentSeverity,
        )

        # Create and save session
        session = ProctorSession.create(
            exam_id="repo-test-exam",
            user_id="repo-test-user",
            tenant_id="test-tenant",
        )

        await session_repo.save(session)

        # Retrieve session
        retrieved = await session_repo.get_by_id(session.id, "test-tenant")
        assert retrieved is not None
        assert retrieved.exam_id == "repo-test-exam"

        # Create and save incident
        incident = ProctorIncident.create(
            session_id=session.id,
            incident_type=IncidentType.PHONE_DETECTED,
            confidence=0.92,
            severity=IncidentSeverity.HIGH,
        )

        await incident_repo.save(incident)

        # Retrieve incidents
        incidents = await incident_repo.get_by_session(session.id)
        assert len(incidents) == 1
        assert incidents[0].incident_type == IncidentType.PHONE_DETECTED

    def test_risk_calculation_workflow(self):
        """Test risk score calculation workflow."""
        from app.domain.entities.proctor_session import ProctorSession
        from app.domain.entities.proctor_incident import (
            ProctorIncident,
            IncidentType,
            IncidentSeverity,
        )

        session = ProctorSession.create(
            exam_id="risk-test",
            user_id="user-001",
            tenant_id="test-tenant",
        )

        # Add various incidents and check risk accumulation
        incidents = [
            (IncidentType.GAZE_AWAY_PROLONGED, IncidentSeverity.LOW, 0.8),
            (IncidentType.GAZE_AWAY_PROLONGED, IncidentSeverity.LOW, 0.7),
            (IncidentType.PHONE_DETECTED, IncidentSeverity.HIGH, 0.9),
        ]

        for inc_type, severity, confidence in incidents:
            incident = ProctorIncident.create(
                session_id=session.id,
                incident_type=inc_type,
                confidence=confidence,
                severity=severity,
            )

            # Calculate risk contribution
            risk_contribution = incident.get_risk_contribution()

            # Update session risk
            new_risk = min(session.risk_score + risk_contribution, 1.0)
            session.update_risk_score(new_risk)
            session.record_incident()

        # High risk incident should significantly increase score
        assert session.risk_score > 0.3
        assert session.incident_count == 3


class TestProctorSecurityWorkflow:
    """Test security-related workflows."""

    def test_input_validation_workflow(self, test_image_base64):
        """Test input validation for security."""
        from app.api.validators.proctor import (
            ImageValidator,
            InputSanitizer,
        )

        # Test valid image validation
        decoded = ImageValidator.validate_base64_image(test_image_base64)
        assert len(decoded) > 0

        # Test invalid image rejection
        with pytest.raises(ValueError):
            ImageValidator.validate_base64_image("not-valid-base64!!!")

        # Test string sanitization
        dirty_string = "<script>alert('xss')</script>Hello"
        clean = InputSanitizer.sanitize_string(dirty_string)
        assert "<script>" not in clean
        assert "Hello" in clean

        # Test metadata sanitization
        dirty_metadata = {
            "name": "<script>bad</script>Good Name",
            "nested": {
                "value": "test<img src=x onerror=alert(1)>",
            },
        }
        clean_metadata = InputSanitizer.sanitize_metadata(dirty_metadata)
        assert "<script>" not in clean_metadata["name"]
        assert "<img" not in clean_metadata["nested"]["value"]

    def test_rate_limiter_config(self):
        """Test rate limiting configuration."""
        from app.infrastructure.resilience.session_rate_limiter import SessionRateLimitConfig

        # Test config defaults
        config = SessionRateLimitConfig()
        assert config.max_frames_per_second > 0
        assert config.max_frames_per_minute > 0

        # Test custom config
        custom_config = SessionRateLimitConfig(
            max_frames_per_second=10,
            max_frames_per_minute=120,
        )
        assert custom_config.max_frames_per_second == 10
        assert custom_config.max_frames_per_minute == 120

    def test_uuid_sanitization(self):
        """Test UUID validation and sanitization."""
        from app.api.validators.proctor import InputSanitizer

        # Valid UUID
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        sanitized = InputSanitizer.sanitize_uuid(valid_uuid)
        assert sanitized == valid_uuid

        # Invalid UUID
        with pytest.raises(ValueError):
            InputSanitizer.sanitize_uuid("not-a-uuid")

        with pytest.raises(ValueError):
            InputSanitizer.sanitize_uuid("'; DROP TABLE users;--")


class TestProctorWebSocketWorkflow:
    """Test WebSocket workflow components."""

    @pytest.mark.asyncio
    async def test_connection_manager_workflow(self):
        """Test WebSocket connection manager."""
        pytest.importorskip("cv2")
        from app.api.websocket.connection_manager import ConnectionManager

        manager = ConnectionManager(max_connections_per_session=3)

        session_id = uuid4()

        # Test connection tracking
        assert manager.get_connection_count() == 0
        assert not manager.is_session_connected(session_id)

        # After connection (simulated), should track
        # Note: Full WebSocket testing requires async client

    def test_frame_header_parsing(self):
        """Test binary frame header parsing."""
        pytest.importorskip("cv2")
        from app.api.websocket.frame_handler import BinaryFrameHeader

        session_id = uuid4()
        frame_number = 42
        timestamp = 1702400000000

        # Create header
        header = BinaryFrameHeader(
            version=1,
            frame_type=0,
            flags=0,
            session_id=session_id,
            frame_number=frame_number,
            timestamp=timestamp,
            payload_size=1024,
        )

        # Serialize and deserialize
        header_bytes = header.to_bytes()
        assert len(header_bytes) == BinaryFrameHeader.HEADER_SIZE

        parsed = BinaryFrameHeader.from_bytes(header_bytes)
        assert parsed.version == 1
        assert parsed.session_id == session_id
        assert parsed.frame_number == frame_number
        assert parsed.timestamp == timestamp


class TestProctorMetricsWorkflow:
    """Test metrics collection workflow."""

    def test_proctor_metrics_collection(self):
        """Test proctoring metrics are recorded correctly."""
        from app.core.metrics.proctoring import ProctorMetrics

        metrics = ProctorMetrics(prefix="test_proctor")

        # Record various metrics
        metrics.record_session_created("tenant-001")
        metrics.record_session_started("tenant-001")
        metrics.record_frame_processed("tenant-001", 50.0)
        metrics.record_incident("tenant-001", "gaze_away", "low")
        metrics.record_risk_score("tenant-001", 0.25)

        # Metrics should be recorded without errors
        # In production, we'd verify Prometheus registry values


class TestProctorConfigWorkflow:
    """Test configuration workflow."""

    def test_config_settings_validation(self):
        """Test that config settings are properly validated."""
        # Test that settings can be imported without errors
        from app.core.config import settings

        # Check proctoring settings exist
        assert hasattr(settings, "PROCTOR_ENABLED")
        assert hasattr(settings, "PROCTOR_GAZE_ENABLED")
        assert hasattr(settings, "PROCTOR_VERIFICATION_THRESHOLD")

        # Verify defaults are reasonable
        assert settings.PROCTOR_VERIFICATION_THRESHOLD >= 0.0
        assert settings.PROCTOR_VERIFICATION_THRESHOLD <= 1.0


class TestIntegrationScenarios:
    """Integration test scenarios."""

    @pytest.mark.asyncio
    async def test_complete_exam_scenario(self, mock_repositories, test_image_base64):
        """Test a complete exam proctoring scenario."""
        session_repo, incident_repo = mock_repositories

        from app.domain.entities.proctor_session import ProctorSession, SessionStatus
        from app.domain.entities.proctor_incident import (
            ProctorIncident,
            IncidentType,
            IncidentSeverity,
        )

        # 1. Student starts exam - create session
        from app.domain.entities.proctor_session import SessionConfig
        config = SessionConfig(verification_interval_sec=30)
        session = ProctorSession.create(
            exam_id="final-exam-2024",
            user_id="student-12345",
            tenant_id="university-001",
            config=config,
        )
        await session_repo.save(session)

        # 2. Capture baseline and start
        baseline = np.random.randn(512).astype(np.float32)
        session.start(baseline_embedding=baseline)
        await session_repo.save(session)

        assert session.status == SessionStatus.ACTIVE

        # 3. Simulate frame submissions (no incidents)
        for i in range(5):
            session.record_verification(success=True)

        # 4. Simulate incident detection
        incident = ProctorIncident.create(
            session_id=session.id,
            incident_type=IncidentType.GAZE_AWAY_PROLONGED,
            confidence=0.75,
            severity=IncidentSeverity.LOW,
            details={"duration_seconds": 4.0},
        )
        await incident_repo.save(incident)
        session.record_incident()
        session.update_risk_score(0.1)

        # 5. Student completes exam
        session.complete()
        await session_repo.save(session)

        # 6. Generate report data
        final_session = await session_repo.get_by_id(session.id, "university-001")
        incidents = await incident_repo.get_by_session(session.id)

        # Verify final state
        assert final_session.status == SessionStatus.COMPLETED
        assert final_session.verification_count == 5
        assert final_session.incident_count == 1
        assert len(incidents) == 1
        assert final_session.risk_score == 0.1

    @pytest.mark.asyncio
    async def test_suspicious_activity_scenario(self, mock_repositories):
        """Test scenario with suspicious activity leading to termination."""
        session_repo, incident_repo = mock_repositories

        from app.domain.entities.proctor_session import ProctorSession, SessionStatus
        from app.domain.entities.proctor_incident import (
            ProctorIncident,
            IncidentType,
            IncidentSeverity,
        )

        # Create and start session
        session = ProctorSession.create(
            exam_id="secure-exam",
            user_id="suspect-user",
            tenant_id="test-tenant",
        )
        session.start(baseline_embedding=np.random.randn(512).astype(np.float32))
        await session_repo.save(session)

        # Simulate multiple high-severity incidents
        high_risk_incidents = [
            (IncidentType.MULTIPLE_FACES, IncidentSeverity.CRITICAL, 0.95),
            (IncidentType.PHONE_DETECTED, IncidentSeverity.HIGH, 0.88),
            (IncidentType.FACE_NOT_DETECTED, IncidentSeverity.HIGH, 0.99),
        ]

        total_risk = 0.0
        for inc_type, severity, confidence in high_risk_incidents:
            incident = ProctorIncident.create(
                session_id=session.id,
                incident_type=inc_type,
                confidence=confidence,
                severity=severity,
            )
            await incident_repo.save(incident)

            risk_contrib = incident.get_risk_contribution()
            total_risk = min(total_risk + risk_contrib, 1.0)
            session.update_risk_score(total_risk)
            session.record_incident()

        # Check if risk threshold exceeded (assuming 0.8 threshold)
        from app.domain.entities.proctor_session import TerminationReason
        if session.risk_score >= 0.8:
            session.terminate(TerminationReason.CRITICAL_VIOLATION)

        await session_repo.save(session)

        # Verify termination
        final_session = await session_repo.get_by_id(session.id, "test-tenant")
        assert final_session.status == SessionStatus.TERMINATED
        assert final_session.risk_score >= 0.8
        assert final_session.incident_count == 3
