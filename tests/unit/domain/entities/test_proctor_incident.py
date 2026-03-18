"""Unit tests for ProctorIncident entity."""

import pytest
from datetime import datetime
from uuid import uuid4

from app.domain.entities.proctor_incident import (
    IncidentEvidence,
    IncidentSeverity,
    IncidentType,
    ProctorIncident,
    ReviewAction,
    get_default_severity,
)


class TestIncidentType:
    """Tests for incident type enum."""

    def test_incident_types_exist(self):
        """Test that all expected incident types are defined."""
        assert IncidentType.FACE_NOT_DETECTED.value == "face_not_detected"
        assert IncidentType.DEEPFAKE_DETECTED.value == "deepfake_detected"
        assert IncidentType.MULTIPLE_FACES.value == "multiple_faces"
        assert IncidentType.RATE_LIMIT_EXCEEDED.value == "rate_limit_exceeded"


class TestIncidentSeverity:
    """Tests for incident severity."""

    def test_severity_levels(self):
        """Test severity level values."""
        assert IncidentSeverity.LOW.value == "low"
        assert IncidentSeverity.MEDIUM.value == "medium"
        assert IncidentSeverity.HIGH.value == "high"
        assert IncidentSeverity.CRITICAL.value == "critical"


class TestGetDefaultSeverity:
    """Tests for default severity mapping."""

    def test_critical_incidents(self):
        """Test that critical incidents are mapped correctly."""
        assert get_default_severity(IncidentType.MULTIPLE_FACES) == IncidentSeverity.CRITICAL
        assert get_default_severity(IncidentType.FACE_NOT_MATCHED) == IncidentSeverity.CRITICAL
        assert get_default_severity(IncidentType.DEEPFAKE_DETECTED) == IncidentSeverity.CRITICAL

    def test_high_incidents(self):
        """Test that high severity incidents are mapped correctly."""
        assert get_default_severity(IncidentType.PHONE_DETECTED) == IncidentSeverity.HIGH
        assert get_default_severity(IncidentType.LIVENESS_FAILED) == IncidentSeverity.HIGH

    def test_medium_incidents(self):
        """Test that medium severity incidents are mapped correctly."""
        assert get_default_severity(IncidentType.GAZE_AWAY_PROLONGED) == IncidentSeverity.MEDIUM
        assert get_default_severity(IncidentType.RATE_LIMIT_EXCEEDED) == IncidentSeverity.MEDIUM

    def test_low_incidents(self):
        """Test that low severity incidents are mapped correctly."""
        assert get_default_severity(IncidentType.FACE_NOT_DETECTED) == IncidentSeverity.LOW


class TestIncidentEvidence:
    """Tests for IncidentEvidence entity."""

    def test_create_evidence(self):
        """Test evidence creation via factory method."""
        incident_id = uuid4()

        evidence = IncidentEvidence.create(
            incident_id=incident_id,
            evidence_type="image",
            storage_url="s3://bucket/evidence/123.jpg",
            thumbnail_url="s3://bucket/evidence/123_thumb.jpg",
            metadata={"size": 1024},
        )

        assert evidence.id is not None
        assert evidence.incident_id == incident_id
        assert evidence.evidence_type == "image"
        assert evidence.storage_url == "s3://bucket/evidence/123.jpg"
        assert evidence.metadata["size"] == 1024

    def test_evidence_to_dict(self):
        """Test evidence serialization."""
        incident_id = uuid4()
        evidence = IncidentEvidence.create(
            incident_id=incident_id,
            evidence_type="video_clip",
            storage_url="s3://bucket/clip.mp4",
        )

        data = evidence.to_dict()

        assert data["incident_id"] == str(incident_id)
        assert data["evidence_type"] == "video_clip"
        assert "created_at" in data


class TestProctorIncident:
    """Tests for ProctorIncident entity."""

    def test_create_incident(self):
        """Test incident creation via factory method."""
        session_id = uuid4()

        incident = ProctorIncident.create(
            session_id=session_id,
            incident_type=IncidentType.PHONE_DETECTED,
            confidence=0.95,
        )

        assert incident.id is not None
        assert incident.session_id == session_id
        assert incident.incident_type == IncidentType.PHONE_DETECTED
        assert incident.severity == IncidentSeverity.HIGH  # default for phone
        assert incident.confidence == 0.95
        assert incident.reviewed is False

    def test_create_incident_with_severity_override(self):
        """Test incident creation with custom severity."""
        session_id = uuid4()

        incident = ProctorIncident.create(
            session_id=session_id,
            incident_type=IncidentType.PHONE_DETECTED,
            confidence=0.8,
            severity=IncidentSeverity.CRITICAL,  # override
        )

        assert incident.severity == IncidentSeverity.CRITICAL

    def test_create_incident_with_details(self):
        """Test incident creation with details."""
        session_id = uuid4()

        incident = ProctorIncident.create(
            session_id=session_id,
            incident_type=IncidentType.MULTIPLE_FACES,
            confidence=0.99,
            details={"face_count": 3},
        )

        assert incident.details["face_count"] == 3

    def test_incident_validation(self):
        """Test incident validation on creation."""
        with pytest.raises(ValueError, match="confidence must be 0-1"):
            ProctorIncident(
                id=uuid4(),
                session_id=uuid4(),
                incident_type=IncidentType.PHONE_DETECTED,
                severity=IncidentSeverity.HIGH,
                confidence=1.5,
                timestamp=datetime.utcnow(),
            )

    def test_add_evidence(self):
        """Test adding evidence to incident."""
        incident = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.PHONE_DETECTED,
            confidence=0.9,
        )

        evidence = IncidentEvidence.create(
            incident_id=incident.id,
            evidence_type="image",
            storage_url="s3://bucket/img.jpg",
        )

        incident.add_evidence(evidence)

        assert len(incident.evidence) == 1
        assert incident.evidence[0].id == evidence.id

    def test_mark_reviewed(self):
        """Test marking incident as reviewed."""
        incident = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.GAZE_AWAY_PROLONGED,
            confidence=0.8,
        )

        incident.mark_reviewed(
            reviewer="admin@example.com",
            action=ReviewAction.ACKNOWLEDGED,
            notes="User was looking at notes",
        )

        assert incident.reviewed is True
        assert incident.reviewed_at is not None
        assert incident.reviewed_by == "admin@example.com"
        assert incident.review_action == ReviewAction.ACKNOWLEDGED
        assert incident.review_notes == "User was looking at notes"

    def test_risk_contribution(self):
        """Test risk contribution calculation."""
        # Low severity, high confidence
        incident_low = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.FACE_NOT_DETECTED,
            confidence=1.0,
        )
        assert incident_low.get_risk_contribution() == pytest.approx(0.1)

        # Critical severity, high confidence
        incident_critical = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.DEEPFAKE_DETECTED,
            confidence=0.9,
        )
        assert incident_critical.get_risk_contribution() == pytest.approx(0.9)

    def test_is_critical(self):
        """Test critical severity check."""
        critical_incident = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.MULTIPLE_FACES,
            confidence=0.95,
        )
        assert critical_incident.is_critical() is True

        low_incident = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.LOW_QUALITY_FEED,
            confidence=0.7,
        )
        assert low_incident.is_critical() is False

    def test_incident_to_dict(self):
        """Test incident serialization."""
        session_id = uuid4()
        incident = ProctorIncident.create(
            session_id=session_id,
            incident_type=IncidentType.PHONE_DETECTED,
            confidence=0.85,
            details={"label": "cell phone"},
        )

        data = incident.to_dict()

        assert data["session_id"] == str(session_id)
        assert data["incident_type"] == "phone_detected"
        assert data["severity"] == "high"
        assert data["confidence"] == 0.85
        assert data["reviewed"] is False
        assert "risk_contribution" in data
        assert data["details"]["label"] == "cell phone"
