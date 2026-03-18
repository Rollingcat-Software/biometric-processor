"""Unit tests for EnrollMultiImageUseCase."""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from app.application.use_cases.enroll_multi_image import EnrollMultiImageUseCase
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.services.embedding_fusion_service import EmbeddingFusionService
from app.domain.exceptions.enrollment_errors import (
    InvalidImageCountError,
    FusionError,
)
from app.domain.exceptions.face_errors import (
    FaceNotDetectedError,
    PoorImageQualityError,
)


@pytest.fixture
def mock_fusion_service():
    """Create mock fusion service."""
    service = Mock(spec=EmbeddingFusionService)

    # Mock fuse_embeddings to return a fused embedding
    async def mock_fuse(embeddings, quality_scores):
        fused_emb = np.random.randn(128).astype(np.float32)
        fused_emb = fused_emb / np.linalg.norm(fused_emb)
        avg_quality = sum(quality_scores) / len(quality_scores)
        return fused_emb, avg_quality

    service.fuse_embeddings = Mock(side_effect=lambda e, q: mock_fuse(e, q))
    return service


@pytest.fixture
def temp_image_files(tmp_path):
    """Create temporary image files."""
    from PIL import Image

    image_files = []
    for i in range(3):
        img_path = tmp_path / f"test_image_{i}.jpg"
        img = Image.new("RGB", (200, 200), color=(100, 100, 100))
        img.save(img_path)
        image_files.append(str(img_path))

    return image_files


class TestEnrollMultiImageUseCase:
    """Test EnrollMultiImageUseCase."""

    @pytest.mark.asyncio
    async def test_successful_multi_image_enrollment(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test successful multi-image enrollment with 3 images."""
        # Setup use case
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Mock cv2.imread for each image
        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            # Execute
            result = await use_case.execute(
                user_id="test_user_123",
                image_paths=temp_image_files,
                tenant_id="test_tenant",
            )

        # Verify result
        assert result.user_id == "test_user_123"
        assert result.tenant_id == "test_tenant"
        assert result.quality_score > 0
        assert len(result.vector) == 128

        # Verify all images were processed
        assert mock_face_detector.detect.call_count == 3
        assert mock_embedding_extractor.extract.call_count == 3
        assert mock_quality_assessor.assess.call_count == 3

        # Verify fusion was called
        mock_fusion_service.fuse_embeddings.assert_called_once()

        # Verify save was called
        mock_embedding_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrollment_with_minimum_images(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test enrollment with minimum required images (2)."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Use only 2 images
        image_paths = temp_image_files[:2]

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            result = await use_case.execute(
                user_id="test_user_123",
                image_paths=image_paths,
            )

        assert result.user_id == "test_user_123"
        assert mock_face_detector.detect.call_count == 2

    @pytest.mark.asyncio
    async def test_enrollment_too_few_images_raises_error(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test that too few images raises InvalidImageCountError."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Try with only 1 image
        with pytest.raises(InvalidImageCountError):
            await use_case.execute(
                user_id="test_user_123",
                image_paths=[temp_image_files[0]],
            )

    @pytest.mark.asyncio
    async def test_enrollment_too_many_images_raises_error(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test that too many images raises InvalidImageCountError."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Try with 6 images (more than max of 5)
        too_many_images = temp_image_files + temp_image_files  # 6 images

        with pytest.raises(InvalidImageCountError):
            await use_case.execute(
                user_id="test_user_123",
                image_paths=too_many_images,
            )

    @pytest.mark.asyncio
    async def test_enrollment_face_not_detected_in_one_image(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test that FaceNotDetectedError in one image fails enrollment."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Make second image fail face detection
        call_count = [0]

        async def detect_with_failure(image):
            call_count[0] += 1
            if call_count[0] == 2:  # Second image
                raise FaceNotDetectedError()
            return FaceDetectionResult(
                found=True,
                bounding_box=(50, 50, 100, 100),
                landmarks=None,
                confidence=0.95,
            )

        mock_face_detector.detect = AsyncMock(side_effect=detect_with_failure)

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            with pytest.raises(FaceNotDetectedError):
                await use_case.execute(
                    user_id="test_user_123",
                    image_paths=temp_image_files,
                )

    @pytest.mark.asyncio
    async def test_enrollment_poor_quality_in_one_image(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test that poor quality in one image fails enrollment."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Make second image have poor quality
        call_count = [0]

        async def assess_with_poor_quality(face_region):
            call_count[0] += 1
            if call_count[0] == 2:  # Second image
                return QualityAssessment(
                    score=40.0,  # Below threshold
                    blur_score=50.0,
                    lighting_score=60.0,
                    face_size=80,
                    is_acceptable=False,
                )
            return QualityAssessment(
                score=85.0,
                blur_score=150.0,
                lighting_score=120.0,
                face_size=100,
                is_acceptable=True,
            )

        mock_quality_assessor.assess = AsyncMock(side_effect=assess_with_poor_quality)

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            with pytest.raises(PoorImageQualityError):
                await use_case.execute(
                    user_id="test_user_123",
                    image_paths=temp_image_files,
                )

    @pytest.mark.asyncio
    async def test_enrollment_fusion_failure_raises_error(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test that fusion failure raises FusionError."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # Make fusion fail
        mock_fusion_service.fuse_embeddings.side_effect = Exception("Fusion failed")

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            with pytest.raises(FusionError):
                await use_case.execute(
                    user_id="test_user_123",
                    image_paths=temp_image_files,
                )

    @pytest.mark.asyncio
    async def test_enrollment_without_tenant_id(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test enrollment without tenant_id."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            result = await use_case.execute(
                user_id="test_user_123",
                image_paths=temp_image_files,
            )

        assert result.tenant_id is None

    @pytest.mark.asyncio
    async def test_enrollment_invalid_image_path(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
    ):
        """Test that invalid image path raises ValueError."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        # cv2.imread returns None for invalid paths
        with patch("cv2.imread", return_value=None):
            with pytest.raises(ValueError, match="Failed to load image"):
                await use_case.execute(
                    user_id="test_user_123",
                    image_paths=["invalid_path_1.jpg", "invalid_path_2.jpg"],
                )

    @pytest.mark.asyncio
    async def test_use_case_uses_default_fusion_service_if_none_provided(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_files,
    ):
        """Test that use case creates default fusion service if none provided."""
        # Create use case without fusion service
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=None,  # Will create default
        )

        # Verify fusion service was created
        assert use_case._fusion_service is not None
        assert isinstance(use_case._fusion_service, EmbeddingFusionService)

    @pytest.mark.asyncio
    async def test_enrollment_with_five_images(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        tmp_path,
    ):
        """Test enrollment with maximum allowed images (5)."""
        from PIL import Image

        # Create 5 test images
        image_files = []
        for i in range(5):
            img_path = tmp_path / f"test_image_{i}.jpg"
            img = Image.new("RGB", (200, 200), color=(100, 100, 100))
            img.save(img_path)
            image_files.append(str(img_path))

        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            result = await use_case.execute(
                user_id="test_user_123",
                image_paths=image_files,
            )

        assert result.user_id == "test_user_123"
        assert mock_face_detector.detect.call_count == 5
        assert mock_embedding_extractor.extract.call_count == 5
        assert mock_quality_assessor.assess.call_count == 5

    @pytest.mark.asyncio
    async def test_repository_called_with_correct_parameters(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """Test that repository save is called with correct parameters."""
        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            await use_case.execute(
                user_id="test_user_123",
                image_paths=temp_image_files,
                tenant_id="test_tenant",
            )

        # Verify save was called with correct parameters
        mock_embedding_repository.save.assert_called_once()
        call_args = mock_embedding_repository.save.call_args

        assert call_args.kwargs["user_id"] == "test_user_123"
        assert call_args.kwargs["tenant_id"] == "test_tenant"
        assert isinstance(call_args.kwargs["embedding"], np.ndarray)
        assert call_args.kwargs["quality_score"] > 0
