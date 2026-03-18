"""Unit tests for ProctorSession entity."""

import pytest
from uuid import uuid4

import numpy as np

from app.domain.entities.proctor_session import (
    ProctorSession,
    SessionConfig,
    SessionStatus,
    TerminationReason,
)


class TestSessionConfig:
    """Tests for SessionConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SessionConfig()

        assert config.verification_interval_sec == 60
        assert config.verification_threshold == 0.6
        assert config.max_verification_failures == 3
        assert config.enable_deepfake_detection is True
        assert config.enable_session_rate_limiting is True

    def test_config_to_dict(self):
        """Test configuration serialization."""
        config = SessionConfig(
            verification_interval_sec=30,
            gaze_away_threshold_sec=10.0,
        )

        data = config.to_dict()

        assert data["verification_interval_sec"] == 30
        assert data["gaze_away_threshold_sec"] == 10.0
        assert "enable_deepfake_detection" in data

    def test_config_from_dict(self):
        """Test configuration deserialization."""
        data = {
            "verification_interval_sec": 45,
            "risk_threshold_critical": 0.9,
        }

        config = SessionConfig.from_dict(data)

        assert config.verification_interval_sec == 45
        assert config.risk_threshold_critical == 0.9
        assert config.verification_threshold == 0.6  # default


class TestProctorSession:
    """Tests for ProctorSession entity."""

    def test_create_session(self):
        """Test session creation via factory method."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )

        assert session.id is not None
        assert session.exam_id == "exam-123"
        assert session.user_id == "user-456"
        assert session.tenant_id == "tenant-789"
        assert session.status == SessionStatus.CREATED
        assert session.risk_score == 0.0

    def test_create_session_with_config(self):
        """Test session creation with custom config."""
        config = SessionConfig(verification_interval_sec=30)

        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
            config=config,
        )

        assert session.config.verification_interval_sec == 30

    def test_session_validation(self):
        """Test session validation on creation."""
        with pytest.raises(ValueError, match="exam_id is required"):
            ProctorSession(
                id=uuid4(),
                exam_id="",
                user_id="user-456",
                tenant_id="tenant-789",
                config=SessionConfig(),
            )

        with pytest.raises(ValueError, match="risk_score must be 0-1"):
            ProctorSession(
                id=uuid4(),
                exam_id="exam-123",
                user_id="user-456",
                tenant_id="tenant-789",
                config=SessionConfig(),
                risk_score=1.5,
            )

    def test_session_start(self):
        """Test starting a session."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )
        embedding = np.random.rand(512).astype(np.float32)

        assert session.can_start() is True

        session.start(embedding)

        assert session.status == SessionStatus.ACTIVE
        assert session.started_at is not None
        assert session.baseline_embedding is not None
        assert session.can_start() is False

    def test_session_pause_resume(self):
        """Test pausing and resuming a session."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )
        session.start(np.random.rand(512).astype(np.float32))

        assert session.can_pause() is True

        session.pause()

        assert session.status == SessionStatus.PAUSED
        assert session.paused_at is not None
        assert session.can_resume() is True

        session.resume()

        assert session.status == SessionStatus.ACTIVE
        assert session.paused_at is None

    def test_session_complete(self):
        """Test completing a session normally."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )
        session.start(np.random.rand(512).astype(np.float32))

        session.complete()

        assert session.status == SessionStatus.COMPLETED
        assert session.ended_at is not None
        assert session.termination_reason == TerminationReason.NORMAL_COMPLETION
        assert session.is_terminal() is True

    def test_session_terminate(self):
        """Test terminating a session with reason."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )
        session.start(np.random.rand(512).astype(np.float32))

        session.terminate(TerminationReason.CRITICAL_VIOLATION)

        assert session.status == SessionStatus.TERMINATED
        assert session.termination_reason == TerminationReason.CRITICAL_VIOLATION

    def test_session_flag_on_high_risk(self):
        """Test session flagging when risk exceeds threshold."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )
        session.start(np.random.rand(512).astype(np.float32))

        session.update_risk_score(0.9)

        assert session.status == SessionStatus.FLAGGED
        assert session.risk_score == 0.9

    def test_session_verification_tracking(self):
        """Test verification attempt tracking."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )

        session.record_verification(success=True)
        session.record_verification(success=True)
        session.record_verification(success=False)

        assert session.verification_count == 3
        assert session.verification_failures == 1
        assert session.get_verification_success_rate() == pytest.approx(2/3)

    def test_session_duration(self):
        """Test session duration calculation."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )

        assert session.get_duration_seconds() == 0.0

        session.start(np.random.rand(512).astype(np.float32))

        # Duration should be > 0 after start
        assert session.get_duration_seconds() >= 0.0

    def test_session_state_transitions(self):
        """Test that invalid state transitions are prevented."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
        )

        # Cannot pause before starting
        with pytest.raises(ValueError, match="Cannot pause"):
            session.pause()

        # Cannot resume before pausing
        with pytest.raises(ValueError, match="Cannot resume"):
            session.resume()

        session.start(np.random.rand(512).astype(np.float32))

        # Cannot start again
        with pytest.raises(ValueError, match="Cannot start"):
            session.start(np.random.rand(512).astype(np.float32))

    def test_session_to_dict(self):
        """Test session serialization."""
        session = ProctorSession.create(
            exam_id="exam-123",
            user_id="user-456",
            tenant_id="tenant-789",
            metadata={"source": "test"},
        )

        data = session.to_dict()

        assert data["exam_id"] == "exam-123"
        assert data["user_id"] == "user-456"
        assert data["status"] == "created"
        assert data["metadata"]["source"] == "test"
        assert "config" in data
        assert "duration_seconds" in data
