"""Unit tests for EnrollmentSession entity."""

import pytest
import numpy as np
from datetime import datetime

from app.domain.entities.enrollment_session import (
    EnrollmentSession,
    SessionStatus,
    ImageSubmission,
)


class TestImageSubmission:
    """Test ImageSubmission entity."""

    def test_create_valid_image_submission(self):
        """Test creating valid image submission."""
        embedding = np.random.randn(128).astype(np.float32)

        submission = ImageSubmission(
            image_id="img_1",
            quality_score=85.0,
            embedding=embedding,
            submitted_at=datetime.utcnow(),
        )

        assert submission.image_id == "img_1"
        assert submission.quality_score == 85.0
        assert submission.embedding.shape == (128,)

    def test_image_submission_invalid_quality_score(self):
        """Test that invalid quality score raises error."""
        embedding = np.random.randn(128).astype(np.float32)

        # Quality > 100
        with pytest.raises(ValueError, match="quality_score must be 0-100"):
            ImageSubmission(
                image_id="img_1",
                quality_score=110.0,
                embedding=embedding,
                submitted_at=datetime.utcnow(),
            )

        # Quality < 0
        with pytest.raises(ValueError, match="quality_score must be 0-100"):
            ImageSubmission(
                image_id="img_1",
                quality_score=-10.0,
                embedding=embedding,
                submitted_at=datetime.utcnow(),
            )

    def test_image_submission_invalid_embedding(self):
        """Test that invalid embedding raises error."""
        # 2D embedding (should be 1D)
        embedding_2d = np.random.randn(128, 128).astype(np.float32)

        with pytest.raises(ValueError, match="1-dimensional"):
            ImageSubmission(
                image_id="img_1",
                quality_score=85.0,
                embedding=embedding_2d,
                submitted_at=datetime.utcnow(),
            )


class TestEnrollmentSession:
    """Test EnrollmentSession entity."""

    def test_create_new_session(self):
        """Test creating new enrollment session."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            tenant_id="tenant_789",
            min_images=2,
            max_images=5,
        )

        assert session.session_id == "sess_123"
        assert session.user_id == "user_456"
        assert session.tenant_id == "tenant_789"
        assert session.status == SessionStatus.PENDING
        assert session.min_images == 2
        assert session.max_images == 5
        assert len(session.submissions) == 0

    def test_session_validation_empty_session_id(self):
        """Test that empty session_id raises error."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            EnrollmentSession(
                session_id="",
                user_id="user_123",
                status=SessionStatus.PENDING,
            )

    def test_session_validation_empty_user_id(self):
        """Test that empty user_id raises error."""
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            EnrollmentSession(
                session_id="sess_123",
                user_id="",
                status=SessionStatus.PENDING,
            )

    def test_session_validation_invalid_min_max_images(self):
        """Test that invalid min/max images raises error."""
        # min > max
        with pytest.raises(ValueError, match="min_images and max_images"):
            EnrollmentSession(
                session_id="sess_123",
                user_id="user_456",
                status=SessionStatus.PENDING,
                min_images=5,
                max_images=2,
            )

        # min < 2
        with pytest.raises(ValueError, match="min_images and max_images"):
            EnrollmentSession(
                session_id="sess_123",
                user_id="user_456",
                status=SessionStatus.PENDING,
                min_images=1,
                max_images=5,
            )

        # max > 5
        with pytest.raises(ValueError, match="min_images and max_images"):
            EnrollmentSession(
                session_id="sess_123",
                user_id="user_456",
                status=SessionStatus.PENDING,
                min_images=2,
                max_images=10,
            )

    def test_add_submission_to_session(self):
        """Test adding image submission to session."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        embedding = np.random.randn(128).astype(np.float32)

        session.add_submission(
            image_id="img_1",
            quality_score=85.0,
            embedding=embedding,
        )

        assert len(session.submissions) == 1
        assert session.get_submission_count() == 1
        assert session.status == SessionStatus.IN_PROGRESS
        assert session.submissions[0].image_id == "img_1"
        assert session.submissions[0].quality_score == 85.0

    def test_add_multiple_submissions(self):
        """Test adding multiple submissions."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            min_images=2,
            max_images=3,
        )

        for i in range(3):
            embedding = np.random.randn(128).astype(np.float32)
            session.add_submission(
                image_id=f"img_{i}",
                quality_score=80.0 + i,
                embedding=embedding,
            )

        assert session.get_submission_count() == 3
        assert session.is_full()
        assert session.is_ready_for_fusion()

    def test_add_submission_to_completed_session_raises_error(self):
        """Test that adding to completed session raises error."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        session.mark_completed()

        embedding = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="Cannot add submission to completed"):
            session.add_submission(
                image_id="img_1",
                quality_score=85.0,
                embedding=embedding,
            )

    def test_add_submission_to_full_session_raises_error(self):
        """Test that adding to full session raises error."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            max_images=2,
        )

        # Add 2 submissions (max)
        for i in range(2):
            embedding = np.random.randn(128).astype(np.float32)
            session.add_submission(
                image_id=f"img_{i}",
                quality_score=80.0,
                embedding=embedding,
            )

        # Try to add 3rd submission
        embedding = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="already has maximum"):
            session.add_submission(
                image_id="img_3",
                quality_score=80.0,
                embedding=embedding,
            )

    def test_is_ready_for_fusion(self):
        """Test is_ready_for_fusion check."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            min_images=2,
        )

        assert not session.is_ready_for_fusion()

        # Add first submission
        embedding1 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_1", 80.0, embedding1)

        assert not session.is_ready_for_fusion()

        # Add second submission
        embedding2 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_2", 85.0, embedding2)

        assert session.is_ready_for_fusion()

    def test_is_full(self):
        """Test is_full check."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            max_images=2,
        )

        assert not session.is_full()

        embedding1 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_1", 80.0, embedding1)

        assert not session.is_full()

        embedding2 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_2", 85.0, embedding2)

        assert session.is_full()

    def test_get_embeddings(self):
        """Test getting all embeddings from session."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        embeddings = []
        for i in range(3):
            emb = np.random.randn(128).astype(np.float32)
            embeddings.append(emb)
            session.add_submission(f"img_{i}", 80.0, emb)

        retrieved_embeddings = session.get_embeddings()

        assert len(retrieved_embeddings) == 3
        for i in range(3):
            assert np.array_equal(retrieved_embeddings[i], embeddings[i])

    def test_get_quality_scores(self):
        """Test getting all quality scores."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        quality_scores = [80.0, 85.0, 90.0]
        for i, score in enumerate(quality_scores):
            emb = np.random.randn(128).astype(np.float32)
            session.add_submission(f"img_{i}", score, emb)

        retrieved_scores = session.get_quality_scores()

        assert retrieved_scores == quality_scores

    def test_get_average_quality(self):
        """Test calculating average quality score."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        # Add submissions with known quality scores
        quality_scores = [70.0, 80.0, 90.0]
        for i, score in enumerate(quality_scores):
            emb = np.random.randn(128).astype(np.float32)
            session.add_submission(f"img_{i}", score, emb)

        avg_quality = session.get_average_quality()

        expected_avg = sum(quality_scores) / len(quality_scores)
        assert avg_quality == expected_avg

    def test_get_average_quality_empty_session(self):
        """Test average quality for empty session."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        assert session.get_average_quality() == 0.0

    def test_mark_completed(self):
        """Test marking session as completed."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        assert session.status == SessionStatus.PENDING
        assert session.completed_at is None

        session.mark_completed()

        assert session.status == SessionStatus.COMPLETED
        assert session.completed_at is not None
        assert session.updated_at is not None

    def test_mark_failed(self):
        """Test marking session as failed."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        session.mark_failed()

        assert session.status == SessionStatus.FAILED
        assert session.updated_at is not None

    def test_session_lifecycle(self):
        """Test complete session lifecycle."""
        # Create session
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            min_images=2,
            max_images=3,
        )

        assert session.status == SessionStatus.PENDING

        # Add first image
        emb1 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_1", 80.0, emb1)

        assert session.status == SessionStatus.IN_PROGRESS
        assert not session.is_ready_for_fusion()

        # Add second image
        emb2 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_2", 85.0, emb2)

        assert session.is_ready_for_fusion()

        # Add third image
        emb3 = np.random.randn(128).astype(np.float32)
        session.add_submission("img_3", 90.0, emb3)

        assert session.is_full()

        # Complete session
        session.mark_completed()

        assert session.status == SessionStatus.COMPLETED
        assert session.get_submission_count() == 3

    def test_session_status_enum(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.PENDING.value == "pending"
        assert SessionStatus.IN_PROGRESS.value == "in_progress"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"

    def test_session_with_tenant_id(self):
        """Test session creation with tenant_id."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
            tenant_id="tenant_789",
        )

        assert session.tenant_id == "tenant_789"

    def test_session_without_tenant_id(self):
        """Test session creation without tenant_id."""
        session = EnrollmentSession.create_new(
            session_id="sess_123",
            user_id="user_456",
        )

        assert session.tenant_id is None
