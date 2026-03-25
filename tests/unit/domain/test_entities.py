"""Unit tests for domain entities."""

import pytest
import numpy as np
from datetime import datetime, timedelta

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.verification_result import VerificationResult


# ============================================================================
# FaceDetectionResult Tests
# ============================================================================


class TestFaceDetectionResult:
    """Test FaceDetectionResult entity."""

    def test_valid_face_detection_result(self):
        """Test creating valid face detection result."""
        result = FaceDetectionResult(
            found=True,
            bounding_box=(50, 50, 100, 100),
            landmarks=np.array([[30, 40], [60, 40]]),
            confidence=0.95,
        )

        assert result.found is True
        assert result.bounding_box == (50, 50, 100, 100)
        assert result.landmarks is not None
        assert result.confidence == 0.95

    def test_no_face_detected(self):
        """Test creating result when no face detected."""
        result = FaceDetectionResult(
            found=False, bounding_box=None, landmarks=None, confidence=0.0
        )

        assert result.found is False
        assert result.bounding_box is None
        assert result.landmarks is None

    def test_missing_bounding_box_when_found(self):
        """Test that bounding box is required when face is found."""
        with pytest.raises(ValueError, match="Bounding box required"):
            FaceDetectionResult(found=True, bounding_box=None, landmarks=None, confidence=0.9)

    def test_invalid_confidence_too_low(self):
        """Test that confidence below 0 raises error."""
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            FaceDetectionResult(
                found=True, bounding_box=(50, 50, 100, 100), landmarks=None, confidence=-0.1
            )

    def test_invalid_confidence_too_high(self):
        """Test that confidence above 1 raises error."""
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            FaceDetectionResult(
                found=True, bounding_box=(50, 50, 100, 100), landmarks=None, confidence=1.5
            )

    def test_invalid_bounding_box_zero_width(self):
        """Test that zero width bounding box raises error."""
        with pytest.raises(ValueError, match="Invalid bounding box dimensions"):
            FaceDetectionResult(
                found=True, bounding_box=(50, 50, 0, 100), landmarks=None, confidence=0.9
            )

    def test_invalid_bounding_box_negative_height(self):
        """Test that negative height bounding box raises error."""
        with pytest.raises(ValueError, match="Invalid bounding box dimensions"):
            FaceDetectionResult(
                found=True, bounding_box=(50, 50, 100, -10), landmarks=None, confidence=0.9
            )

    def test_get_face_region(self):
        """Test extracting face region from image."""
        result = FaceDetectionResult(
            found=True, bounding_box=(10, 20, 50, 60), landmarks=None, confidence=0.9
        )

        # Create test image (100x100)
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        face_region = result.get_face_region(image)

        # Should extract region of size (60, 50, 3) - height x width x channels
        assert face_region.shape == (60, 50, 3)

    def test_get_face_region_without_bounding_box(self):
        """Test that get_face_region raises error without bounding box."""
        result = FaceDetectionResult(
            found=False, bounding_box=None, landmarks=None, confidence=0.0
        )

        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        with pytest.raises(ValueError, match="No bounding box available"):
            result.get_face_region(image)

    def test_get_face_center(self):
        """Test calculating face center point."""
        result = FaceDetectionResult(
            found=True, bounding_box=(10, 20, 100, 80), landmarks=None, confidence=0.9
        )

        center = result.get_face_center()

        # Center should be at (10 + 100//2, 20 + 80//2) = (60, 60)
        assert center == (60, 60)

    def test_get_face_center_without_bounding_box(self):
        """Test that get_face_center returns None without bounding box."""
        result = FaceDetectionResult(
            found=False, bounding_box=None, landmarks=None, confidence=0.0
        )

        center = result.get_face_center()
        assert center is None

    def test_immutability(self):
        """Test that FaceDetectionResult is immutable."""
        result = FaceDetectionResult(
            found=True, bounding_box=(50, 50, 100, 100), landmarks=None, confidence=0.9
        )

        with pytest.raises(Exception):  # dataclass frozen raises FrozenInstanceError
            result.confidence = 0.8


# ============================================================================
# QualityAssessment Tests
# ============================================================================


class TestQualityAssessment:
    """Test QualityAssessment entity."""

    def test_valid_quality_assessment_good(self):
        """Test creating valid good quality assessment."""
        assessment = QualityAssessment(
            score=85.0,
            blur_score=150.0,
            lighting_score=120.0,
            face_size=100,
            is_acceptable=True,
        )

        assert assessment.score == 85.0
        assert assessment.blur_score == 150.0
        assert assessment.lighting_score == 120.0
        assert assessment.face_size == 100
        assert assessment.is_acceptable is True

    def test_valid_quality_assessment_poor(self):
        """Test creating valid poor quality assessment."""
        assessment = QualityAssessment(
            score=30.0,
            blur_score=50.0,
            lighting_score=40.0,
            face_size=50,
            is_acceptable=False,
        )

        assert assessment.score == 30.0
        assert assessment.is_acceptable is False

    def test_invalid_score_too_low(self):
        """Test that score below 0 raises error."""
        with pytest.raises(ValueError, match="Score must be 0-100"):
            QualityAssessment(
                score=-10.0,
                blur_score=100.0,
                lighting_score=100.0,
                face_size=80,
                is_acceptable=False,
            )

    def test_invalid_score_too_high(self):
        """Test that score above 100 raises error."""
        with pytest.raises(ValueError, match="Score must be 0-100"):
            QualityAssessment(
                score=150.0,
                blur_score=100.0,
                lighting_score=100.0,
                face_size=80,
                is_acceptable=True,
            )

    def test_invalid_negative_blur_score(self):
        """Test that negative blur score raises error."""
        with pytest.raises(ValueError, match="Blur score cannot be negative"):
            QualityAssessment(
                score=80.0,
                blur_score=-50.0,
                lighting_score=100.0,
                face_size=80,
                is_acceptable=True,
            )

    def test_invalid_negative_face_size(self):
        """Test that negative face size raises error."""
        with pytest.raises(ValueError, match="Face size cannot be negative"):
            QualityAssessment(
                score=80.0,
                blur_score=100.0,
                lighting_score=100.0,
                face_size=-10,
                is_acceptable=True,
            )

    def test_get_quality_level_poor(self):
        """Test quality level for poor score."""
        assessment = QualityAssessment(
            score=30.0,
            blur_score=50.0,
            lighting_score=60.0,
            face_size=70,
            is_acceptable=False,
        )

        assert assessment.get_quality_level() == "poor"

    def test_get_quality_level_fair(self):
        """Test quality level for fair score."""
        assessment = QualityAssessment(
            score=60.0,
            blur_score=100.0,
            lighting_score=100.0,
            face_size=80,
            is_acceptable=True,
        )

        assert assessment.get_quality_level() == "fair"

    def test_get_quality_level_good(self):
        """Test quality level for good score."""
        assessment = QualityAssessment(
            score=85.0,
            blur_score=150.0,
            lighting_score=120.0,
            face_size=100,
            is_acceptable=True,
        )

        assert assessment.get_quality_level() == "good"

    def test_is_blurry_default_threshold(self):
        """Test blur detection with default threshold."""
        assessment = QualityAssessment(
            score=60.0,
            blur_score=80.0,
            lighting_score=100.0,
            face_size=80,
            is_acceptable=True,
        )

        assert assessment.is_blurry() is True

    def test_is_not_blurry(self):
        """Test image that is not blurry."""
        assessment = QualityAssessment(
            score=85.0,
            blur_score=150.0,
            lighting_score=120.0,
            face_size=100,
            is_acceptable=True,
        )

        assert assessment.is_blurry() is False

    def test_is_blurry_custom_threshold(self):
        """Test blur detection with custom threshold."""
        assessment = QualityAssessment(
            score=80.0,
            blur_score=120.0,
            lighting_score=100.0,
            face_size=90,
            is_acceptable=True,
        )

        assert assessment.is_blurry(blur_threshold=150.0) is True
        assert assessment.is_blurry(blur_threshold=100.0) is False

    def test_is_too_small_default_threshold(self):
        """Test face size check with default threshold."""
        assessment = QualityAssessment(
            score=60.0,
            blur_score=100.0,
            lighting_score=100.0,
            face_size=70,
            is_acceptable=False,
        )

        assert assessment.is_too_small() is True

    def test_is_not_too_small(self):
        """Test face size that is acceptable."""
        assessment = QualityAssessment(
            score=85.0,
            blur_score=150.0,
            lighting_score=120.0,
            face_size=100,
            is_acceptable=True,
        )

        assert assessment.is_too_small() is False

    def test_get_issues_multiple(self):
        """Test getting multiple quality issues."""
        assessment = QualityAssessment(
            score=35.0,
            blur_score=70.0,
            lighting_score=40.0,
            face_size=60,
            is_acceptable=False,
        )

        issues = assessment.get_issues()

        assert "blur" in issues
        assert "face_size" in issues
        assert "lighting" in issues
        assert issues["blur"]["score"] == 70.0
        assert issues["face_size"]["size"] == 60
        assert issues["lighting"]["score"] == 40.0

    def test_get_issues_none(self):
        """Test getting issues when quality is good."""
        assessment = QualityAssessment(
            score=90.0,
            blur_score=200.0,
            lighting_score=150.0,
            face_size=120,
            is_acceptable=True,
        )

        issues = assessment.get_issues()
        assert len(issues) == 0

    def test_to_dict(self):
        """Test converting to dictionary."""
        assessment = QualityAssessment(
            score=85.0,
            blur_score=150.0,
            lighting_score=120.0,
            face_size=100,
            is_acceptable=True,
        )

        result = assessment.to_dict()

        assert result["score"] == 85.0
        assert result["blur_score"] == 150.0
        assert result["lighting_score"] == 120.0
        assert result["face_size"] == 100
        assert result["is_acceptable"] is True
        assert result["quality_level"] == "good"
        assert "issues" in result

    def test_immutability(self):
        """Test that QualityAssessment is immutable."""
        assessment = QualityAssessment(
            score=85.0,
            blur_score=150.0,
            lighting_score=120.0,
            face_size=100,
            is_acceptable=True,
        )

        with pytest.raises(Exception):  # frozen dataclass
            assessment.score = 90.0


# ============================================================================
# FaceEmbedding Tests
# ============================================================================


class TestFaceEmbedding:
    """Test FaceEmbedding entity."""

    def test_valid_face_embedding(self):
        """Test creating valid face embedding."""
        vector = np.random.randn(128).astype(np.float32)
        created = datetime.utcnow()

        embedding = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=created,
        )

        assert embedding.user_id == "test_user_123"
        assert len(embedding.vector) == 128
        assert embedding.quality_score == 85.0
        assert embedding.created_at == created
        assert embedding.updated_at is None
        assert embedding.tenant_id is None

    def test_face_embedding_with_tenant(self):
        """Test creating face embedding with tenant ID."""
        vector = np.random.randn(128).astype(np.float32)

        embedding = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
            tenant_id="tenant_xyz",
        )

        assert embedding.tenant_id == "tenant_xyz"

    def test_invalid_empty_user_id(self):
        """Test that empty user_id raises error."""
        vector = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="user_id cannot be empty"):
            FaceEmbedding(
                user_id="",
                vector=vector,
                quality_score=85.0,
                created_at=datetime.utcnow(),
            )

    def test_invalid_none_vector(self):
        """Test that None vector raises error."""
        with pytest.raises(ValueError, match="vector must be 1-dimensional"):
            FaceEmbedding(
                user_id="test_user_123",
                vector=None,
                quality_score=85.0,
                created_at=datetime.utcnow(),
            )

    def test_invalid_2d_vector(self):
        """Test that 2D vector raises error."""
        vector = np.random.randn(10, 10).astype(np.float32)

        with pytest.raises(ValueError, match="vector must be 1-dimensional"):
            FaceEmbedding(
                user_id="test_user_123",
                vector=vector,
                quality_score=85.0,
                created_at=datetime.utcnow(),
            )

    def test_invalid_quality_score_too_low(self):
        """Test that quality score below 0 raises error."""
        vector = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="quality_score must be 0-100"):
            FaceEmbedding(
                user_id="test_user_123",
                vector=vector,
                quality_score=-10.0,
                created_at=datetime.utcnow(),
            )

    def test_invalid_quality_score_too_high(self):
        """Test that quality score above 100 raises error."""
        vector = np.random.randn(128).astype(np.float32)

        with pytest.raises(ValueError, match="quality_score must be 0-100"):
            FaceEmbedding(
                user_id="test_user_123",
                vector=vector,
                quality_score=150.0,
                created_at=datetime.utcnow(),
            )

    def test_equality_same_user(self):
        """Test equality based on user_id."""
        vector1 = np.random.randn(128).astype(np.float32)
        vector2 = np.random.randn(128).astype(np.float32)

        emb1 = FaceEmbedding(
            user_id="test_user_123",
            vector=vector1,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        emb2 = FaceEmbedding(
            user_id="test_user_123",
            vector=vector2,
            quality_score=90.0,
            created_at=datetime.utcnow(),
        )

        # Same user_id means same entity, even with different vectors
        assert emb1 == emb2

    def test_equality_different_user(self):
        """Test inequality for different users."""
        vector = np.random.randn(128).astype(np.float32)

        emb1 = FaceEmbedding(
            user_id="user_1",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        emb2 = FaceEmbedding(
            user_id="user_2",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        assert emb1 != emb2

    def test_equality_different_tenant(self):
        """Test inequality for different tenants."""
        vector = np.random.randn(128).astype(np.float32)

        emb1 = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
            tenant_id="tenant_a",
        )

        emb2 = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
            tenant_id="tenant_b",
        )

        # Same user but different tenant = different entity
        assert emb1 != emb2

    def test_hash_consistency(self):
        """Test that hash is consistent for same user."""
        vector = np.random.randn(128).astype(np.float32)

        emb1 = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        emb2 = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        assert hash(emb1) == hash(emb2)

    def test_get_embedding_dimension(self):
        """Test getting embedding dimension."""
        vector = np.random.randn(512).astype(np.float32)

        embedding = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        assert embedding.get_embedding_dimension() == 512

    def test_is_fresh_within_limit(self):
        """Test freshness check for recent embedding."""
        vector = np.random.randn(128).astype(np.float32)
        created = datetime.utcnow() - timedelta(days=100)

        embedding = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=created,
        )

        assert embedding.is_fresh(max_age_days=365) is True

    def test_is_not_fresh_exceeded_limit(self):
        """Test freshness check for old embedding."""
        vector = np.random.randn(128).astype(np.float32)
        created = datetime.utcnow() - timedelta(days=400)

        embedding = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=created,
        )

        assert embedding.is_fresh(max_age_days=365) is False

    def test_to_list(self):
        """Test converting vector to list."""
        vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)

        embedding = FaceEmbedding(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            created_at=datetime.utcnow(),
        )

        result = embedding.to_list()

        assert isinstance(result, list)
        assert len(result) == 3
        assert result == [1.0, 2.0, 3.0]

    def test_create_new_factory_method(self):
        """Test factory method for creating new embedding."""
        vector = np.random.randn(128).astype(np.float32)

        embedding = FaceEmbedding.create_new(
            user_id="test_user_123", vector=vector, quality_score=85.0
        )

        assert embedding.user_id == "test_user_123"
        assert len(embedding.vector) == 128
        assert embedding.quality_score == 85.0
        assert embedding.created_at is not None
        assert embedding.updated_at is None
        assert embedding.tenant_id is None

    def test_create_new_with_tenant(self):
        """Test factory method with tenant ID."""
        vector = np.random.randn(128).astype(np.float32)

        embedding = FaceEmbedding.create_new(
            user_id="test_user_123",
            vector=vector,
            quality_score=85.0,
            tenant_id="tenant_xyz",
        )

        assert embedding.tenant_id == "tenant_xyz"

    def test_update(self):
        """Test updating embedding."""
        vector1 = np.random.randn(128).astype(np.float32)
        vector2 = np.random.randn(128).astype(np.float32)

        embedding = FaceEmbedding.create_new(
            user_id="test_user_123", vector=vector1, quality_score=80.0
        )

        assert embedding.updated_at is None

        # Update with new vector and quality
        embedding.update(vector=vector2, quality_score=90.0)

        assert embedding.quality_score == 90.0
        assert embedding.updated_at is not None
        assert np.array_equal(embedding.vector, vector2)

    def test_update_dimension_mismatch(self):
        """Test that updating with different dimension raises error."""
        vector1 = np.random.randn(128).astype(np.float32)
        vector2 = np.random.randn(256).astype(np.float32)

        embedding = FaceEmbedding.create_new(
            user_id="test_user_123", vector=vector1, quality_score=80.0
        )

        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            embedding.update(vector=vector2, quality_score=90.0)


# ============================================================================
# LivenessResult Tests
# ============================================================================


class TestLivenessResult:
    """Test LivenessResult entity."""

    def test_valid_liveness_result_pass(self):
        """Test creating valid passing liveness result."""
        result = LivenessResult(
            is_live=True,
            score=92.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.is_live is True
        assert result.score == 92.0
        assert result.liveness_score == 92.0
        assert result.challenge == "smile"
        assert result.challenge_completed is True

    def test_legacy_liveness_score_alias_still_works(self):
        """Test backward-compatible construction via liveness_score."""
        result = LivenessResult(
            is_live=True,
            liveness_score=88.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.score == 88.0
        assert result.liveness_score == 88.0

    def test_valid_liveness_result_fail(self):
        """Test creating valid failing liveness result."""
        result = LivenessResult(
            is_live=False,
            liveness_score=45.0,
            challenge="blink",
            challenge_completed=False,
        )

        assert result.is_live is False
        assert result.liveness_score == 45.0
        assert result.challenge == "blink"
        assert result.challenge_completed is False

    def test_invalid_liveness_score_too_low(self):
        """Test that liveness score below 0 raises error."""
        with pytest.raises(ValueError, match="Liveness score must be 0-100"):
            LivenessResult(
                is_live=False,
                liveness_score=-10.0,
                challenge="smile",
                challenge_completed=False,
            )

    def test_invalid_liveness_score_too_high(self):
        """Test that liveness score above 100 raises error."""
        with pytest.raises(ValueError, match="Liveness score must be 0-100"):
            LivenessResult(
                is_live=True,
                liveness_score=150.0,
                challenge="smile",
                challenge_completed=True,
            )

    def test_invalid_empty_challenge(self):
        """Test that empty challenge raises error."""
        with pytest.raises(ValueError, match="Challenge type cannot be empty"):
            LivenessResult(
                is_live=True,
                liveness_score=90.0,
                challenge="",
                challenge_completed=True,
            )

    def test_get_confidence_level_low(self):
        """Test confidence level for low score."""
        result = LivenessResult(
            is_live=False,
            liveness_score=30.0,
            challenge="smile",
            challenge_completed=False,
        )

        assert result.get_confidence_level() == "low"

    def test_get_confidence_level_medium(self):
        """Test confidence level for medium score."""
        result = LivenessResult(
            is_live=True,
            liveness_score=70.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.get_confidence_level() == "medium"

    def test_get_confidence_level_high(self):
        """Test confidence level for high score."""
        result = LivenessResult(
            is_live=True,
            liveness_score=95.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.get_confidence_level() == "high"

    def test_is_spoof_suspected_default_threshold(self):
        """Test spoof detection with default threshold."""
        result = LivenessResult(
            is_live=False,
            liveness_score=40.0,
            challenge="smile",
            challenge_completed=False,
        )

        assert result.is_spoof_suspected() is True

    def test_is_not_spoof_suspected(self):
        """Test when spoof is not suspected."""
        result = LivenessResult(
            is_live=True,
            liveness_score=85.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.is_spoof_suspected() is False

    def test_is_spoof_suspected_custom_threshold(self):
        """Test spoof detection with custom threshold."""
        result = LivenessResult(
            is_live=True,
            liveness_score=70.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.is_spoof_suspected(threshold=80.0) is True
        assert result.is_spoof_suspected(threshold=60.0) is False

    def test_requires_additional_verification_true(self):
        """Test when additional verification is required."""
        result = LivenessResult(
            is_live=True,
            liveness_score=70.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.requires_additional_verification() is True

    def test_requires_additional_verification_false_high_score(self):
        """Test when additional verification not required (high score)."""
        result = LivenessResult(
            is_live=True,
            liveness_score=90.0,
            challenge="smile",
            challenge_completed=True,
        )

        assert result.requires_additional_verification() is False

    def test_requires_additional_verification_false_low_score(self):
        """Test when additional verification not required (too low)."""
        result = LivenessResult(
            is_live=False,
            liveness_score=30.0,
            challenge="smile",
            challenge_completed=False,
        )

        # Score too low (below 50), doesn't require additional - just reject
        assert result.requires_additional_verification() is False

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = LivenessResult(
            is_live=True,
            liveness_score=85.0,
            challenge="smile",
            challenge_completed=True,
        )

        data = result.to_dict()

        assert data["is_live"] is True
        assert data["score"] == 85.0
        assert data["liveness_score"] == 85.0
        assert data["challenge"] == "smile"
        assert data["challenge_completed"] is True
        assert data["confidence_level"] == "high"
        assert data["spoof_suspected"] is False
        assert data["requires_additional_verification"] is False

    def test_immutability(self):
        """Test that LivenessResult is immutable."""
        result = LivenessResult(
            is_live=True,
            liveness_score=90.0,
            challenge="smile",
            challenge_completed=True,
        )

        with pytest.raises(Exception):  # frozen dataclass
            result.is_live = False


# ============================================================================
# VerificationResult Tests
# ============================================================================


class TestVerificationResult:
    """Test VerificationResult entity."""

    def test_valid_verification_result_match(self):
        """Test creating valid matching verification result."""
        result = VerificationResult(
            verified=True, confidence=0.87, distance=0.13, threshold=0.6
        )

        assert result.verified is True
        assert result.confidence == 0.87
        assert result.distance == 0.13
        assert result.threshold == 0.6

    def test_valid_verification_result_no_match(self):
        """Test creating valid non-matching verification result."""
        result = VerificationResult(
            verified=False, confidence=0.35, distance=0.75, threshold=0.6
        )

        assert result.verified is False
        assert result.confidence == 0.35
        assert result.distance == 0.75

    def test_invalid_confidence_too_low(self):
        """Test that confidence below 0 raises error."""
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            VerificationResult(verified=False, confidence=-0.1, distance=0.8, threshold=0.6)

    def test_invalid_confidence_too_high(self):
        """Test that confidence above 1 raises error."""
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            VerificationResult(verified=True, confidence=1.5, distance=0.2, threshold=0.6)

    def test_invalid_negative_distance(self):
        """Test that negative distance raises error."""
        with pytest.raises(ValueError, match="Distance cannot be negative"):
            VerificationResult(verified=True, confidence=0.9, distance=-0.1, threshold=0.6)

    def test_invalid_negative_threshold(self):
        """Test that negative threshold raises error."""
        with pytest.raises(ValueError, match="Threshold cannot be negative"):
            VerificationResult(verified=True, confidence=0.9, distance=0.2, threshold=-0.6)

    def test_inconsistent_verified_true_but_distance_high(self):
        """Test that inconsistent verified=True with high distance raises error."""
        with pytest.raises(ValueError, match="Inconsistent verification result"):
            VerificationResult(
                verified=True,  # Says verified
                confidence=0.9,
                distance=0.8,  # But distance > threshold
                threshold=0.6,
            )

    def test_inconsistent_verified_false_but_distance_low(self):
        """Test that inconsistent verified=False with low distance raises error."""
        with pytest.raises(ValueError, match="Inconsistent verification result"):
            VerificationResult(
                verified=False,  # Says not verified
                confidence=0.9,
                distance=0.3,  # But distance < threshold
                threshold=0.6,
            )

    def test_get_confidence_level_low(self):
        """Test confidence level for low confidence."""
        result = VerificationResult(
            verified=False, confidence=0.35, distance=0.75, threshold=0.6
        )

        assert result.get_confidence_level() == "low"

    def test_get_confidence_level_medium(self):
        """Test confidence level for medium confidence."""
        result = VerificationResult(
            verified=True, confidence=0.65, distance=0.35, threshold=0.6
        )

        assert result.get_confidence_level() == "medium"

    def test_get_confidence_level_high(self):
        """Test confidence level for high confidence."""
        result = VerificationResult(
            verified=True, confidence=0.95, distance=0.05, threshold=0.6
        )

        assert result.get_confidence_level() == "high"

    def test_is_strong_match_true(self):
        """Test strong match detection."""
        result = VerificationResult(
            verified=True, confidence=0.95, distance=0.05, threshold=0.6
        )

        assert result.is_strong_match(threshold=0.9) is True

    def test_is_strong_match_false_low_confidence(self):
        """Test strong match false when confidence too low."""
        result = VerificationResult(
            verified=True, confidence=0.85, distance=0.15, threshold=0.6
        )

        assert result.is_strong_match(threshold=0.9) is False

    def test_is_strong_match_false_not_verified(self):
        """Test strong match false when not verified."""
        result = VerificationResult(
            verified=False, confidence=0.45, distance=0.65, threshold=0.6
        )

        assert result.is_strong_match() is False

    def test_is_weak_match_true(self):
        """Test weak match detection when close to threshold."""
        result = VerificationResult(
            verified=True,
            confidence=0.65,
            distance=0.57,  # Close to threshold of 0.6
            threshold=0.6,
        )

        assert result.is_weak_match() is True

    def test_is_weak_match_false_strong_match(self):
        """Test weak match false when match is strong."""
        result = VerificationResult(
            verified=True, confidence=0.95, distance=0.05, threshold=0.6
        )

        assert result.is_weak_match() is False

    def test_is_weak_match_false_not_verified(self):
        """Test weak match false when not verified."""
        result = VerificationResult(
            verified=False, confidence=0.45, distance=0.65, threshold=0.6
        )

        assert result.is_weak_match() is False

    def test_get_similarity_percentage(self):
        """Test converting confidence to percentage."""
        result = VerificationResult(
            verified=True, confidence=0.87, distance=0.13, threshold=0.6
        )

        assert result.get_similarity_percentage() == 87.0

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = VerificationResult(
            verified=True, confidence=0.87, distance=0.13, threshold=0.6
        )

        data = result.to_dict()

        assert data["verified"] is True
        assert data["confidence"] == 0.87
        assert data["distance"] == 0.13
        assert data["threshold"] == 0.6
        assert data["confidence_level"] == "high"  # 0.87 >= 0.8 = high
        assert data["similarity_percentage"] == 87.0
        assert "strong_match" in data
        assert "weak_match" in data

    def test_immutability(self):
        """Test that VerificationResult is immutable."""
        result = VerificationResult(
            verified=True, confidence=0.87, distance=0.13, threshold=0.6
        )

        with pytest.raises(Exception):  # frozen dataclass
            result.verified = False
