"""Unit tests for EnrollMultiImageUseCase."""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.application.use_cases.enroll_multi_image import EnrollMultiImageUseCase
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.liveness_result import LivenessResult
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
from app.domain.exceptions.liveness_errors import LivenessCheckFailedError


@pytest.fixture
def mock_fusion_service():
    """Create mock fusion service.

    NOTE: ``EmbeddingFusionService.fuse_embeddings`` is a **synchronous**
    method on the current production class (see
    app/domain/services/embedding_fusion_service.py) and the use case calls
    it with keyword arguments ``embeddings=...`` and ``quality_scores=...``
    (see enroll_multi_image.py:244). The earlier mock returned a coroutine
    via a positional ``lambda e, q:`` and broke under both rules.
    """
    service = Mock(spec=EmbeddingFusionService)

    def mock_fuse(embeddings, quality_scores):
        fused_emb = np.random.randn(128).astype(np.float32)
        fused_emb = fused_emb / np.linalg.norm(fused_emb)
        avg_quality = sum(quality_scores) / len(quality_scores)
        return fused_emb, avg_quality

    service.fuse_embeddings = Mock(side_effect=mock_fuse)
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

        # Verify result.
        # NOTE: ``MultiImageEnrollmentResult`` exposes ``fused_quality_score``
        # (property over face_embedding.quality_score) — there is no
        # standalone ``quality_score`` attribute. The raw embedding lives at
        # ``face_embedding.vector``. See
        # ``app/domain/entities/multi_image_enrollment_result.py``.
        assert result.user_id == "test_user_123"
        assert result.tenant_id == "test_tenant"
        assert result.fused_quality_score > 0
        assert len(result.face_embedding.vector) == 128

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
    async def test_enrollment_face_not_detected_falls_back_to_full_image(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """FaceNotDetectedError in one image triggers a full-image fallback.

        NOTE (2026-05-12): production behaviour changed — the use case now
        treats OpenCV-side face detection as soft. If the server-side detector
        cannot find a face (typical for side-angle multi-image submissions
        where the client/MediaPipe has already confirmed and cropped), the
        full input image is used as the face region instead of raising. See
        ``app/application/use_cases/enroll_multi_image.py`` (the
        ``except FaceNotDetectedError`` branch around line 152). The test was
        previously written against the older "fail-loud" policy.
        """
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

            # Fallback path completes enrollment instead of raising.
            result = await use_case.execute(
                user_id="test_user_123",
                image_paths=temp_image_files,
            )

        assert result.user_id == "test_user_123"
        assert mock_face_detector.detect.call_count == 3
        # All three images contributed an embedding (image 2 via fallback).
        assert mock_embedding_extractor.extract.call_count == 3
        mock_embedding_repository.save.assert_called_once()

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


def _live_result(score: float, is_live: bool) -> LivenessResult:
    """Build a passive-liveness LivenessResult fixture for the gate tests."""
    return LivenessResult(
        is_live=is_live,
        score=score,
        challenge="passive",
        challenge_completed=True,
    )


class TestEnrollMultiImageLivenessGate:
    """The /enroll/multi path must run the SAME server-authoritative passive
    liveness check that single-image /enroll runs (fail-closed), so a photo or
    screen replay can no longer be enrolled via the multi-image path.

    The liveness backend verdict is mocked at the CheckLivenessUseCase boundary
    (the exact use case single-/enroll calls), so these tests assert the WIRING
    + fail-closed policy without booting UniFace MiniFASNet / ONNX.
    """

    @pytest.mark.asyncio
    async def test_rejects_spoof_frame_fail_closed(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """A single non-live (spoof) frame rejects the WHOLE enrollment and
        nothing is persisted (fail-closed). The spoof frame is the second of
        three, proving every frame is gated, not just the first."""
        call_count = [0]

        async def liveness_side_effect(image_path):
            call_count[0] += 1
            # Second frame is a photo/screen replay → not live.
            return _live_result(score=18.0, is_live=call_count[0] != 2)

        liveness_use_case = Mock(spec=CheckLivenessUseCase)
        liveness_use_case.execute = AsyncMock(side_effect=liveness_side_effect)

        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
            liveness_use_case=liveness_use_case,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            with pytest.raises(LivenessCheckFailedError):
                await use_case.execute(
                    user_id="spoofer",
                    image_paths=temp_image_files,
                )

        # Gate ran on frame 1 (live) then frame 2 (spoof) → stopped there.
        assert liveness_use_case.execute.await_count == 2
        # Fail-closed: no embedding persisted on a spoof frame.
        mock_embedding_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_frame_spoof_rejects_immediately(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """A spoof on the very first frame short-circuits before any embedding
        work happens."""
        liveness_use_case = Mock(spec=CheckLivenessUseCase)
        liveness_use_case.execute = AsyncMock(
            return_value=_live_result(score=5.0, is_live=False)
        )

        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
            liveness_use_case=liveness_use_case,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            with pytest.raises(LivenessCheckFailedError):
                await use_case.execute(
                    user_id="spoofer",
                    image_paths=temp_image_files,
                )

        assert liveness_use_case.execute.await_count == 1
        # Liveness gate sits BEFORE detection/quality/extraction.
        mock_face_detector.detect.assert_not_called()
        mock_embedding_extractor.extract.assert_not_called()
        mock_embedding_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_accepts_all_live_frames(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """When every frame is live, enrollment proceeds normally and the gate
        was exercised once per frame."""
        liveness_use_case = Mock(spec=CheckLivenessUseCase)
        liveness_use_case.execute = AsyncMock(
            return_value=_live_result(score=92.0, is_live=True)
        )

        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
            liveness_use_case=liveness_use_case,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(
                0, 255, (200, 200, 3), dtype=np.uint8
            )

            result = await use_case.execute(
                user_id="real_user",
                image_paths=temp_image_files,
            )

        assert result.user_id == "real_user"
        assert liveness_use_case.execute.await_count == len(temp_image_files)
        mock_embedding_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_gate_skipped_when_disabled(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_quality_assessor,
        mock_embedding_repository,
        mock_fusion_service,
        temp_image_files,
    ):
        """ENROLL_LIVENESS_ENABLED=False is an explicit operator escape hatch:
        the liveness backend is never called and a spoof frame would pass. This
        mirrors the single-/enroll gate's config flag."""
        liveness_use_case = Mock(spec=CheckLivenessUseCase)
        liveness_use_case.execute = AsyncMock(
            return_value=_live_result(score=1.0, is_live=False)
        )

        use_case = EnrollMultiImageUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            quality_assessor=mock_quality_assessor,
            repository=mock_embedding_repository,
            fusion_service=mock_fusion_service,
            liveness_use_case=liveness_use_case,
        )

        with patch(
            "app.application.use_cases.enroll_multi_image.settings.ENROLL_LIVENESS_ENABLED",
            False,
        ):
            with patch("cv2.imread") as mock_imread:
                mock_imread.return_value = np.random.randint(
                    0, 255, (200, 200, 3), dtype=np.uint8
                )

                result = await use_case.execute(
                    user_id="bypass_user",
                    image_paths=temp_image_files,
                )

        assert result.user_id == "bypass_user"
        liveness_use_case.execute.assert_not_called()
        mock_embedding_repository.save.assert_called_once()
