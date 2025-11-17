"""Unit tests for application use cases."""

import pytest
import numpy as np
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.application.use_cases.check_liveness import CheckLivenessUseCase

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.verification_result import VerificationResult

from app.domain.exceptions.face_errors import (
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
)
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError


# ============================================================================
# EnrollFaceUseCase Tests
# ============================================================================


class TestEnrollFaceUseCase:
    """Test EnrollFaceUseCase."""

    @pytest.mark.asyncio
    async def test_successful_enrollment(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """Test successful face enrollment."""
        # Setup
        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        # Execute
        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(
                user_id="test_user_123",
                image_path=temp_image_file,
                tenant_id="test_tenant",
            )

        # Verify
        assert result.user_id == "test_user_123"
        assert result.tenant_id == "test_tenant"
        assert result.quality_score > 0
        assert len(result.vector) == 128

        # Verify dependencies were called
        mock_face_detector.detect.assert_called_once()
        mock_embedding_extractor.extract.assert_called_once()
        mock_quality_assessor.assess.assert_called_once()
        mock_embedding_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrollment_without_tenant(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Test enrollment without tenant ID."""
        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(
                user_id="test_user_123",
                image_path=temp_image_file,
            )

        assert result.tenant_id is None

    @pytest.mark.asyncio
    async def test_enrollment_fails_with_poor_quality(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Test that enrollment fails when quality is poor."""
        # Setup poor quality assessment
        poor_quality = QualityAssessment(
            score=40.0,
            blur_score=50.0,
            lighting_score=60.0,
            face_size=50,
            is_acceptable=False,
        )
        mock_quality_assessor.assess = AsyncMock(return_value=poor_quality)

        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        # Execute and verify exception
        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(PoorImageQualityError) as exc_info:
                await use_case.execute(
                    user_id="test_user_123",
                    image_path=temp_image_file,
                )

        # Verify error details
        assert exc_info.value.quality_score == 40.0
        assert exc_info.value.error_code == "POOR_IMAGE_QUALITY"

        # Repository save should NOT be called
        mock_embedding_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrollment_fails_with_no_face(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Test that enrollment fails when no face is detected."""
        # Setup detector to raise exception
        mock_face_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(FaceNotDetectedError):
                await use_case.execute(
                    user_id="test_user_123",
                    image_path=temp_image_file,
                )

        # Quality assessment and extraction should NOT be called
        mock_quality_assessor.assess.assert_not_called()
        mock_embedding_extractor.extract.assert_not_called()
        mock_embedding_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrollment_fails_with_multiple_faces(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Test that enrollment fails when multiple faces are detected."""
        mock_face_detector.detect = AsyncMock(side_effect=MultipleFacesError(count=3))

        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(MultipleFacesError) as exc_info:
                await use_case.execute(
                    user_id="test_user_123",
                    image_path=temp_image_file,
                )

        assert exc_info.value.face_count == 3

    @pytest.mark.asyncio
    async def test_enrollment_fails_with_invalid_image_path(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
    ):
        """Test that enrollment fails with invalid image path."""
        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = None  # Simulates failed image load

            with pytest.raises(ValueError, match="Failed to load image"):
                await use_case.execute(
                    user_id="test_user_123",
                    image_path="/nonexistent/path.jpg",
                )

    @pytest.mark.asyncio
    async def test_enrollment_saves_correct_data(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """Test that enrollment saves correct data to repository."""
        use_case = EnrollFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            await use_case.execute(
                user_id="user_456",
                image_path=temp_image_file,
                tenant_id="tenant_789",
            )

        # Verify save was called with correct arguments
        save_call = mock_embedding_repository.save.call_args
        assert save_call.kwargs["user_id"] == "user_456"
        assert save_call.kwargs["tenant_id"] == "tenant_789"
        assert isinstance(save_call.kwargs["embedding"], np.ndarray)
        assert save_call.kwargs["quality_score"] > 0


# ============================================================================
# VerifyFaceUseCase Tests
# ============================================================================


class TestVerifyFaceUseCase:
    """Test VerifyFaceUseCase."""

    @pytest.mark.asyncio
    async def test_successful_verification_match(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """Test successful verification with matching faces."""
        # Setup repository to return stored embedding
        mock_embedding_repository.find_by_user_id = AsyncMock(return_value=sample_embedding)

        use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(
                user_id="test_user_123",
                image_path=temp_image_file,
            )

        # Verify result
        assert isinstance(result, VerificationResult)
        assert result.verified is True
        assert result.confidence > 0
        assert result.distance >= 0

        # Verify dependencies were called
        mock_face_detector.detect.assert_called_once()
        mock_embedding_extractor.extract.assert_called_once()
        mock_similarity_calculator.calculate.assert_called_once()
        mock_embedding_repository.find_by_user_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_verification_with_tenant_id(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """Test verification with tenant ID."""
        mock_embedding_repository.find_by_user_id = AsyncMock(return_value=sample_embedding)

        use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(
                user_id="test_user_123",
                image_path=temp_image_file,
                tenant_id="tenant_xyz",
            )

        # Verify repository was called with tenant_id
        call_args = mock_embedding_repository.find_by_user_id.call_args
        assert call_args[0][0] == "test_user_123"
        assert call_args[0][1] == "tenant_xyz"

    @pytest.mark.asyncio
    async def test_verification_no_match(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """Test verification with non-matching faces."""
        # Setup for no match
        mock_similarity_calculator.calculate = Mock(return_value=0.8)  # High distance
        mock_similarity_calculator.get_threshold = Mock(return_value=0.6)
        mock_similarity_calculator.get_confidence = Mock(return_value=0.2)  # Low confidence
        mock_embedding_repository.find_by_user_id = AsyncMock(return_value=sample_embedding)

        use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(
                user_id="test_user_123",
                image_path=temp_image_file,
            )

        assert result.verified is False
        assert result.distance == 0.8
        assert result.confidence == 0.2

    @pytest.mark.asyncio
    async def test_verification_fails_no_stored_embedding(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Test verification fails when no stored embedding exists."""
        # Setup repository to return None
        mock_embedding_repository.find_by_user_id = AsyncMock(return_value=None)

        use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(EmbeddingNotFoundError) as exc_info:
                await use_case.execute(
                    user_id="unknown_user",
                    image_path=temp_image_file,
                )

        assert exc_info.value.user_id == "unknown_user"

        # Similarity calculation should NOT be called
        mock_similarity_calculator.calculate.assert_not_called()

    @pytest.mark.asyncio
    async def test_verification_fails_with_no_face(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Test verification fails when no face detected."""
        mock_face_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

        use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(FaceNotDetectedError):
                await use_case.execute(
                    user_id="test_user_123",
                    image_path=temp_image_file,
                )

        # Subsequent steps should NOT be called
        mock_embedding_extractor.extract.assert_not_called()
        mock_embedding_repository.find_by_user_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_verification_fails_with_invalid_image(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
    ):
        """Test verification fails with invalid image path."""
        use_case = VerifyFaceUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            repository=mock_embedding_repository,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = None

            with pytest.raises(ValueError, match="Failed to load image"):
                await use_case.execute(
                    user_id="test_user_123",
                    image_path="/invalid/path.jpg",
                )


# ============================================================================
# CheckLivenessUseCase Tests
# ============================================================================


class TestCheckLivenessUseCase:
    """Test CheckLivenessUseCase."""

    @pytest.mark.asyncio
    async def test_successful_liveness_check_pass(
        self,
        mock_face_detector,
        mock_liveness_detector,
        temp_image_file,
        liveness_result_pass,
    ):
        """Test successful liveness check that passes."""
        use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=mock_liveness_detector,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(image_path=temp_image_file)

        # Verify result
        assert isinstance(result, LivenessResult)
        assert result.is_live is True
        assert result.liveness_score > 0
        assert result.challenge is not None

        # Verify dependencies were called
        mock_face_detector.detect.assert_called_once()
        mock_liveness_detector.check_liveness.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_liveness_check_fail(
        self,
        mock_face_detector,
        mock_liveness_detector,
        temp_image_file,
        liveness_result_fail,
    ):
        """Test successful liveness check that fails."""
        mock_liveness_detector.check_liveness = AsyncMock(return_value=liveness_result_fail)

        use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=mock_liveness_detector,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            result = await use_case.execute(image_path=temp_image_file)

        assert result.is_live is False
        assert result.liveness_score < 80.0

    @pytest.mark.asyncio
    async def test_liveness_check_fails_with_no_face(
        self,
        mock_face_detector,
        mock_liveness_detector,
        temp_image_file,
    ):
        """Test liveness check fails when no face detected."""
        mock_face_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

        use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=mock_liveness_detector,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(FaceNotDetectedError):
                await use_case.execute(image_path=temp_image_file)

        # Liveness detection should NOT be called
        mock_liveness_detector.check_liveness.assert_not_called()

    @pytest.mark.asyncio
    async def test_liveness_check_fails_with_multiple_faces(
        self,
        mock_face_detector,
        mock_liveness_detector,
        temp_image_file,
    ):
        """Test liveness check fails with multiple faces."""
        mock_face_detector.detect = AsyncMock(side_effect=MultipleFacesError(count=2))

        use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=mock_liveness_detector,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(MultipleFacesError):
                await use_case.execute(image_path=temp_image_file)

    @pytest.mark.asyncio
    async def test_liveness_check_fails_with_invalid_image(
        self,
        mock_face_detector,
        mock_liveness_detector,
    ):
        """Test liveness check fails with invalid image path."""
        use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=mock_liveness_detector,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = None

            with pytest.raises(ValueError, match="Failed to load image"):
                await use_case.execute(image_path="/invalid/path.jpg")

    @pytest.mark.asyncio
    async def test_liveness_check_passes_image_to_detector(
        self,
        mock_face_detector,
        mock_liveness_detector,
        temp_image_file,
    ):
        """Test that liveness check passes the full image to liveness detector."""
        use_case = CheckLivenessUseCase(
            detector=mock_face_detector,
            liveness_detector=mock_liveness_detector,
        )

        test_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = test_image

            await use_case.execute(image_path=temp_image_file)

        # Verify liveness detector received the image
        call_args = mock_liveness_detector.check_liveness.call_args
        assert isinstance(call_args[0][0], np.ndarray)
