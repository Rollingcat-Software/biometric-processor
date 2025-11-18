"""Unit tests for batch processing use cases."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from app.application.use_cases.batch_process import (
    BatchEnrollmentUseCase,
    BatchOperationStatus,
    BatchVerificationUseCase,
    EnrollmentItem,
    VerificationItem,
)
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.exceptions.face_errors import FaceNotDetectedError, MultipleFacesError


class TestBatchEnrollmentUseCase:
    """Tests for BatchEnrollmentUseCase."""

    @pytest.fixture
    def mock_face_detector(self):
        """Create mock face detector."""
        detector = AsyncMock()
        detection = FaceDetectionResult(
            found=True,
            bounding_box=(10, 10, 80, 80),
            confidence=0.99,
            landmarks=None,
        )
        detector.detect.return_value = detection
        return detector

    @pytest.fixture
    def mock_embedding_extractor(self):
        """Create mock embedding extractor."""
        extractor = AsyncMock()
        extractor.extract.return_value = np.random.rand(512).astype(np.float32)
        return extractor

    @pytest.fixture
    def mock_quality_assessor(self):
        """Create mock quality assessor."""
        assessor = AsyncMock()
        assessor.assess.return_value = QualityAssessment(
            score=85.0,
            blur_score=90.0,
            lighting_score=80.0,
            face_size=100,
            is_acceptable=True,
        )
        assessor.get_minimum_acceptable_score.return_value = 70.0
        return assessor

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        repo = AsyncMock()
        repo.find_by_user_id.return_value = None
        repo.save.return_value = None
        return repo

    @pytest.fixture
    def use_case(
        self, mock_face_detector, mock_embedding_extractor, mock_quality_assessor, mock_repository
    ):
        """Create batch enrollment use case with mocks."""
        return BatchEnrollmentUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_repository,
            max_concurrent=3,
        )

    @pytest.fixture
    def test_images(self):
        """Create temporary test images."""
        images = []
        temp_dir = tempfile.mkdtemp()

        for i in range(3):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[10:90, 10:90] = [128, 128, 128]  # Face-like region
            path = os.path.join(temp_dir, f"test_{i}.jpg")
            cv2.imwrite(path, img)
            images.append(path)

        yield images

        # Cleanup
        for path in images:
            if os.path.exists(path):
                os.unlink(path)
        os.rmdir(temp_dir)

    @pytest.mark.asyncio
    async def test_batch_enrollment_success(self, use_case, test_images, mock_repository):
        """Test successful batch enrollment."""
        items = [EnrollmentItem(user_id=f"user_{i}", image_path=test_images[i]) for i in range(3)]

        result = await use_case.execute(items)

        assert result.total_items == 3
        assert result.successful == 3
        assert result.failed == 0
        assert result.skipped == 0
        assert len(result.results) == 3

        for item_result in result.results:
            assert item_result.status == BatchOperationStatus.SUCCESS
            assert item_result.data is not None
            assert "quality_score" in item_result.data

    @pytest.mark.asyncio
    async def test_batch_enrollment_skip_duplicates(self, use_case, test_images, mock_repository):
        """Test skipping duplicate users."""

        # Make first user exist
        async def find_by_user_id(user_id, tenant_id=None):
            if user_id == "user_0":
                return MagicMock()  # Return existing embedding
            return None

        mock_repository.find_by_user_id = find_by_user_id

        items = [EnrollmentItem(user_id=f"user_{i}", image_path=test_images[i]) for i in range(3)]

        result = await use_case.execute(items, skip_duplicates=True)

        assert result.total_items == 3
        assert result.successful == 2
        assert result.skipped == 1

        # Check that first user was skipped
        skipped_results = [r for r in result.results if r.status == BatchOperationStatus.SKIPPED]
        assert len(skipped_results) == 1
        assert skipped_results[0].item_id == "user_0"

    @pytest.mark.asyncio
    async def test_batch_enrollment_face_not_detected(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_repository,
        test_images,
    ):
        """Test handling face not detected."""
        # Make first image fail face detection
        call_count = [0]

        async def detect_side_effect(image):
            call_count[0] += 1
            if call_count[0] == 1:
                raise FaceNotDetectedError()
            return FaceDetectionResult(
                found=True,
                bounding_box=(10, 10, 80, 80),
                confidence=0.99,
                landmarks=None,
            )

        mock_face_detector.detect = detect_side_effect

        use_case = BatchEnrollmentUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_repository,
        )

        items = [EnrollmentItem(user_id=f"user_{i}", image_path=test_images[i]) for i in range(3)]

        result = await use_case.execute(items)

        assert result.failed >= 1

        failed_results = [r for r in result.results if r.status == BatchOperationStatus.FAILED]
        assert any(r.error_code == "NO_FACE_DETECTED" for r in failed_results)

    @pytest.mark.asyncio
    async def test_batch_enrollment_quality_check_fails(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_repository,
        test_images,
    ):
        """Test handling poor quality images."""
        # Make quality check fail for all images
        mock_quality_assessor.assess.return_value = QualityAssessment(
            score=30.0,
            blur_score=25.0,
            lighting_score=30.0,
            face_size=80,
            is_acceptable=False,
        )

        use_case = BatchEnrollmentUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_repository,
        )

        items = [EnrollmentItem(user_id=f"user_{i}", image_path=test_images[i]) for i in range(3)]

        result = await use_case.execute(items)

        assert result.failed == 3

        for item_result in result.results:
            assert item_result.status == BatchOperationStatus.FAILED
            assert item_result.error_code == "POOR_QUALITY"

    @pytest.mark.asyncio
    async def test_batch_enrollment_with_tenant_id(self, use_case, test_images):
        """Test batch enrollment with tenant isolation."""
        items = [
            EnrollmentItem(user_id=f"user_{i}", image_path=test_images[i], tenant_id="tenant_1")
            for i in range(3)
        ]

        result = await use_case.execute(items)

        assert result.successful == 3

    @pytest.mark.asyncio
    async def test_batch_enrollment_invalid_image_path(self, use_case):
        """Test handling invalid image paths."""
        items = [EnrollmentItem(user_id="user_1", image_path="/nonexistent/path.jpg")]

        result = await use_case.execute(items)

        assert result.failed == 1
        assert result.results[0].error_code == "IMAGE_LOAD_ERROR"


class TestBatchVerificationUseCase:
    """Tests for BatchVerificationUseCase."""

    @pytest.fixture
    def mock_face_detector(self):
        """Create mock face detector."""
        detector = AsyncMock()
        detection = FaceDetectionResult(
            found=True,
            bounding_box=(10, 10, 80, 80),
            confidence=0.99,
            landmarks=None,
        )
        detector.detect.return_value = detection
        return detector

    @pytest.fixture
    def mock_embedding_extractor(self):
        """Create mock embedding extractor."""
        extractor = AsyncMock()
        extractor.extract.return_value = np.random.rand(512).astype(np.float32)
        return extractor

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository with stored embeddings."""
        repo = AsyncMock()

        # Return stored embedding
        stored = MagicMock()
        stored.embedding = np.random.rand(512).astype(np.float32)
        repo.find_by_user_id.return_value = stored

        return repo

    @pytest.fixture
    def mock_similarity_calculator(self):
        """Create mock similarity calculator."""
        calc = MagicMock()
        calc.calculate.return_value = 0.3  # Good match
        return calc

    @pytest.fixture
    def use_case(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_repository,
        mock_similarity_calculator,
    ):
        """Create batch verification use case with mocks."""
        return BatchVerificationUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=mock_repository,
            similarity_calculator=mock_similarity_calculator,
            max_concurrent=3,
            default_threshold=0.6,
        )

    @pytest.fixture
    def test_images(self):
        """Create temporary test images."""
        images = []
        temp_dir = tempfile.mkdtemp()

        for i in range(3):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[10:90, 10:90] = [128, 128, 128]
            path = os.path.join(temp_dir, f"verify_{i}.jpg")
            cv2.imwrite(path, img)
            images.append(path)

        yield images

        # Cleanup
        for path in images:
            if os.path.exists(path):
                os.unlink(path)
        os.rmdir(temp_dir)

    @pytest.mark.asyncio
    async def test_batch_verification_success(self, use_case, test_images):
        """Test successful batch verification."""
        items = [
            VerificationItem(item_id=f"verify_{i}", user_id=f"user_{i}", image_path=test_images[i])
            for i in range(3)
        ]

        result = await use_case.execute(items)

        assert result.total_items == 3
        assert result.successful == 3
        assert result.failed == 0
        assert len(result.results) == 3

        for item_result in result.results:
            assert item_result.status == BatchOperationStatus.SUCCESS
            assert item_result.data is not None
            assert "is_match" in item_result.data
            assert "distance" in item_result.data
            assert "confidence" in item_result.data

    @pytest.mark.asyncio
    async def test_batch_verification_user_not_found(
        self, mock_face_detector, mock_embedding_extractor, mock_similarity_calculator, test_images
    ):
        """Test verification when user not enrolled."""
        # Return None for user lookup
        mock_repository = AsyncMock()
        mock_repository.find_by_user_id.return_value = None

        use_case = BatchVerificationUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=mock_repository,
            similarity_calculator=mock_similarity_calculator,
        )

        items = [
            VerificationItem(item_id="verify_1", user_id="unknown_user", image_path=test_images[0])
        ]

        result = await use_case.execute(items)

        assert result.failed == 1
        assert result.results[0].error_code == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_batch_verification_mixed_results(
        self, mock_face_detector, mock_embedding_extractor, mock_similarity_calculator, test_images
    ):
        """Test batch with mixed match/no-match results."""
        mock_repository = AsyncMock()

        # Create stored embedding
        stored = MagicMock()
        stored.embedding = np.random.rand(512).astype(np.float32)
        mock_repository.find_by_user_id.return_value = stored

        # Make distance vary
        call_count = [0]

        def distance_side_effect(probe, stored):
            call_count[0] += 1
            if call_count[0] == 1:
                return 0.3  # Match
            elif call_count[0] == 2:
                return 0.8  # No match
            else:
                return 0.4  # Match

        mock_similarity_calculator.calculate = distance_side_effect

        use_case = BatchVerificationUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=mock_repository,
            similarity_calculator=mock_similarity_calculator,
            default_threshold=0.6,
        )

        items = [
            VerificationItem(item_id=f"verify_{i}", user_id=f"user_{i}", image_path=test_images[i])
            for i in range(3)
        ]

        result = await use_case.execute(items)

        assert result.successful == 3  # All processed successfully

        # Check match results
        matches = [r for r in result.results if r.data and r.data.get("is_match")]
        no_matches = [r for r in result.results if r.data and not r.data.get("is_match")]

        assert len(matches) == 2
        assert len(no_matches) == 1

    @pytest.mark.asyncio
    async def test_batch_verification_custom_threshold(
        self, use_case, test_images, mock_similarity_calculator
    ):
        """Test verification with custom threshold."""
        mock_similarity_calculator.calculate.return_value = 0.5

        items = [VerificationItem(item_id="verify_1", user_id="user_1", image_path=test_images[0])]

        # With default threshold 0.6, should match
        result = await use_case.execute(items, threshold=0.6)
        assert result.results[0].data["is_match"] == True

        # With lower threshold 0.4, should not match
        result = await use_case.execute(items, threshold=0.4)
        assert result.results[0].data["is_match"] == False

    @pytest.mark.asyncio
    async def test_batch_verification_with_tenant_id(self, use_case, test_images):
        """Test batch verification with tenant isolation."""
        items = [
            VerificationItem(
                item_id=f"verify_{i}",
                user_id=f"user_{i}",
                image_path=test_images[i],
                tenant_id="tenant_1",
            )
            for i in range(3)
        ]

        result = await use_case.execute(items)

        assert result.successful == 3

    @pytest.mark.asyncio
    async def test_batch_verification_face_not_detected(
        self, mock_embedding_extractor, mock_repository, mock_similarity_calculator, test_images
    ):
        """Test handling face not detected during verification."""
        mock_face_detector = AsyncMock()
        mock_face_detector.detect.side_effect = FaceNotDetectedError()

        use_case = BatchVerificationUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            repository=mock_repository,
            similarity_calculator=mock_similarity_calculator,
        )

        items = [VerificationItem(item_id="verify_1", user_id="user_1", image_path=test_images[0])]

        result = await use_case.execute(items)

        assert result.failed == 1
        assert result.results[0].error_code == "NO_FACE_DETECTED"
