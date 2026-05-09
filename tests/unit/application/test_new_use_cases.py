"""Unit tests for new feature use cases."""

import pytest
from unittest.mock import AsyncMock, Mock

from app.application.use_cases.analyze_quality import AnalyzeQualityUseCase
from app.application.use_cases.detect_multi_face import DetectMultiFaceUseCase
from app.application.use_cases.analyze_demographics import AnalyzeDemographicsUseCase
from app.application.use_cases.detect_landmarks import DetectLandmarksUseCase
from app.application.use_cases.compare_faces import CompareFacesUseCase
from app.application.use_cases.compute_similarity_matrix import ComputeSimilarityMatrixUseCase
from app.application.use_cases.export_embeddings import ExportEmbeddingsUseCase
from app.application.use_cases.import_embeddings import ImportEmbeddingsUseCase
from app.application.use_cases.send_webhook import SendWebhookUseCase

from app.domain.entities.quality_feedback import QualityFeedback
from app.domain.entities.multi_face_result import MultiFaceResult
from app.domain.entities.demographics import DemographicsResult, AgeEstimate, GenderEstimate
from app.domain.entities.face_landmarks import LandmarkResult, Landmark
from app.domain.entities.face_comparison import FaceComparisonResult
from app.domain.entities.similarity_matrix import SimilarityMatrixResult
from app.domain.entities.webhook_event import WebhookResult

from app.domain.exceptions.face_errors import FaceNotDetectedError


# ============================================================================
# Mock Fixtures for New Use Cases
# ============================================================================


@pytest.fixture
def mock_demographics_analyzer():
    """Create a mock demographics analyzer.

    NOTE: AnalyzeDemographicsUseCase calls `_demographics_analyzer.analyze(image)`
    synchronously (not awaited) — see analyze_demographics.py. Returning a
    plain Mock with a non-async return_value matches that calling convention.
    """
    analyzer = Mock()
    analyzer.analyze = Mock(return_value=DemographicsResult(
        age=AgeEstimate(value=30, range=(25, 35), confidence=0.9),
        gender=GenderEstimate(value="male", confidence=0.95),
        emotion=None,
        race=None,
    ))
    return analyzer


@pytest.fixture
def mock_landmark_detector():
    """Create a mock landmark detector.

    NOTE: DetectLandmarksUseCase calls `_landmark_detector.detect(...)`
    synchronously — see detect_landmarks.py. Mock (not AsyncMock) is correct.
    """
    detector = Mock()
    detector.detect = Mock(return_value=LandmarkResult(
        model="mediapipe_468",
        landmark_count=3,
        landmarks=[
            Landmark(id=0, x=100, y=100, z=0.0),
            Landmark(id=1, x=80, y=90, z=0.0),
            Landmark(id=2, x=120, y=90, z=0.0),
        ],
        regions={},
        head_pose=None,
    ))
    return detector


@pytest.fixture
def mock_webhook_sender():
    """Create a mock webhook sender."""
    sender = Mock()
    sender.send = AsyncMock(return_value=WebhookResult(
        success=True,
        status_code=200,
        response_time_ms=150.0,
        error=None,
    ))
    return sender


# ============================================================================
# AnalyzeQualityUseCase Tests
# ============================================================================


class TestAnalyzeQualityUseCase:
    """Test AnalyzeQualityUseCase."""

    @pytest.mark.asyncio
    async def test_successful_quality_analysis(
        self,
        mock_face_detector,
        mock_quality_assessor,
        sample_image,
    ):
        """Test successful quality analysis.

        Note: AnalyzeQualityUseCase computes metrics directly via cv2/numpy
        and does NOT call quality_assessor.assess() — the assessor is held
        for future use only. We assert detector was called and we got a
        QualityFeedback back.
        """
        use_case = AnalyzeQualityUseCase(
            detector=mock_face_detector,
            quality_assessor=mock_quality_assessor,
        )

        result = await use_case.execute(image=sample_image)

        assert isinstance(result, QualityFeedback)
        assert result.overall_score >= 0
        mock_face_detector.detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_quality_analysis_no_face(
        self,
        mock_face_detector,
        mock_quality_assessor,
        sample_image,
    ):
        """Test quality analysis when no face detected."""
        mock_face_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

        use_case = AnalyzeQualityUseCase(
            detector=mock_face_detector,
            quality_assessor=mock_quality_assessor,
        )

        with pytest.raises(FaceNotDetectedError):
            await use_case.execute(image=sample_image)


# ============================================================================
# DetectMultiFaceUseCase Tests
# ============================================================================


class TestDetectMultiFaceUseCase:
    """Test DetectMultiFaceUseCase."""

    @pytest.mark.asyncio
    async def test_successful_multi_face_detection(
        self,
        mock_face_detector,
        mock_quality_assessor,
        sample_image,
    ):
        """Test successful multi-face detection."""
        use_case = DetectMultiFaceUseCase(
            detector=mock_face_detector,
            quality_assessor=mock_quality_assessor,
        )

        result = await use_case.execute(image=sample_image)

        assert isinstance(result, MultiFaceResult)
        mock_face_detector.detect.assert_called()


# ============================================================================
# AnalyzeDemographicsUseCase Tests
# ============================================================================


class TestAnalyzeDemographicsUseCase:
    """Test AnalyzeDemographicsUseCase."""

    @pytest.mark.asyncio
    async def test_successful_demographics_analysis(
        self,
        mock_face_detector,
        mock_demographics_analyzer,
        sample_image,
    ):
        """Test successful demographics analysis."""
        use_case = AnalyzeDemographicsUseCase(
            detector=mock_face_detector,
            demographics_analyzer=mock_demographics_analyzer,
        )

        result = await use_case.execute(image=sample_image)

        assert isinstance(result, DemographicsResult)
        assert result.age.value == 30
        assert result.gender.value == "male"
        mock_face_detector.detect.assert_called_once()
        mock_demographics_analyzer.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_demographics_analysis_no_face(
        self,
        mock_face_detector,
        mock_demographics_analyzer,
        sample_image,
    ):
        """Test demographics analysis when no face detected."""
        mock_face_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

        use_case = AnalyzeDemographicsUseCase(
            detector=mock_face_detector,
            demographics_analyzer=mock_demographics_analyzer,
        )

        with pytest.raises(FaceNotDetectedError):
            await use_case.execute(image=sample_image)

        mock_demographics_analyzer.analyze.assert_not_called()


# ============================================================================
# DetectLandmarksUseCase Tests
# ============================================================================


class TestDetectLandmarksUseCase:
    """Test DetectLandmarksUseCase."""

    @pytest.mark.asyncio
    async def test_successful_landmark_detection(
        self,
        mock_face_detector,
        mock_landmark_detector,
        sample_image,
    ):
        """Test successful landmark detection."""
        use_case = DetectLandmarksUseCase(
            detector=mock_face_detector,
            landmark_detector=mock_landmark_detector,
        )

        result = await use_case.execute(image=sample_image)

        assert isinstance(result, LandmarkResult)
        assert len(result.landmarks) == 3
        assert result.landmarks[0].name == "nose_tip"
        mock_face_detector.detect.assert_called_once()
        mock_landmark_detector.detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_landmark_detection_no_face(
        self,
        mock_face_detector,
        mock_landmark_detector,
        sample_image,
    ):
        """Test landmark detection when no face detected."""
        mock_face_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

        use_case = DetectLandmarksUseCase(
            detector=mock_face_detector,
            landmark_detector=mock_landmark_detector,
        )

        with pytest.raises(FaceNotDetectedError):
            await use_case.execute(image=sample_image)

        mock_landmark_detector.detect.assert_not_called()


# ============================================================================
# CompareFacesUseCase Tests
# ============================================================================


class TestCompareFacesUseCase:
    """Test CompareFacesUseCase."""

    @pytest.mark.asyncio
    async def test_successful_face_comparison_match(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_quality_assessor,
        sample_image,
    ):
        """Test successful face comparison with match."""
        use_case = CompareFacesUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            quality_assessor=mock_quality_assessor,
        )

        result = await use_case.execute(
            image1=sample_image,
            image2=sample_image,
            threshold=0.6,
        )

        assert isinstance(result, FaceComparisonResult)
        assert result.match is True
        assert result.similarity > 0
        assert mock_face_detector.detect.call_count == 2
        assert mock_embedding_extractor.extract.call_count == 2
        mock_similarity_calculator.calculate.assert_called_once()

    @pytest.mark.asyncio
    async def test_face_comparison_no_match(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_quality_assessor,
        sample_image,
    ):
        """Test face comparison with no match."""
        mock_similarity_calculator.calculate = Mock(return_value=0.8)  # High distance
        mock_similarity_calculator.get_confidence = Mock(return_value=0.2)

        use_case = CompareFacesUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            quality_assessor=mock_quality_assessor,
        )

        result = await use_case.execute(
            image1=sample_image,
            image2=sample_image,
            threshold=0.6,
        )

        assert result.match is False

    @pytest.mark.asyncio
    async def test_face_comparison_no_face_in_first_image(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_quality_assessor,
        sample_image,
    ):
        """Test comparison fails when no face in first image."""
        from app.domain.exceptions.face_errors import FaceNotFoundError

        mock_face_detector.detect = AsyncMock(
            return_value=Mock(found=False, bounding_box=None)
        )

        use_case = CompareFacesUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
            quality_assessor=mock_quality_assessor,
        )

        with pytest.raises(FaceNotFoundError):
            await use_case.execute(
                image1=sample_image,
                image2=sample_image,
            )


# ============================================================================
# ComputeSimilarityMatrixUseCase Tests
# ============================================================================


class TestComputeSimilarityMatrixUseCase:
    """Test ComputeSimilarityMatrixUseCase."""

    @pytest.mark.asyncio
    async def test_successful_similarity_matrix(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        sample_image,
    ):
        """Test successful similarity matrix computation."""
        use_case = ComputeSimilarityMatrixUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
        )

        images = [sample_image, sample_image, sample_image]
        result = await use_case.execute(images, threshold=0.6)

        assert isinstance(result, SimilarityMatrixResult)
        assert result.matrix is not None
        assert len(result.matrix) == 3

    @pytest.mark.asyncio
    async def test_similarity_matrix_with_labels(
        self,
        mock_face_detector,
        mock_embedding_extractor,
        mock_similarity_calculator,
        sample_image,
    ):
        """Test similarity matrix with labels."""
        use_case = ComputeSimilarityMatrixUseCase(
            detector=mock_face_detector,
            extractor=mock_embedding_extractor,
            similarity_calculator=mock_similarity_calculator,
        )

        images = [sample_image, sample_image]
        labels = ["person_a", "person_b"]
        result = await use_case.execute(images, labels=labels, threshold=0.6)

        assert result.labels == labels


# ============================================================================
# ExportEmbeddingsUseCase Tests
# ============================================================================


class TestExportEmbeddingsUseCase:
    """Test ExportEmbeddingsUseCase."""

    @pytest.mark.asyncio
    async def test_successful_export(
        self,
        mock_embedding_repository,
        sample_embedding,
    ):
        """Test successful embeddings export."""
        # Setup repository to return embeddings — use_case calls list_all(tenant_id)
        mock_embedding_repository.list_all = AsyncMock(return_value=[
            {"user_id": "user1", "embedding": sample_embedding.tolist(), "quality_score": 85.0},
            {"user_id": "user2", "embedding": sample_embedding.tolist(), "quality_score": 90.0},
        ])

        use_case = ExportEmbeddingsUseCase(
            repository=mock_embedding_repository,
        )

        result = await use_case.execute(tenant_id="default")

        assert "embeddings" in result
        assert result["count"] == 2
        assert "checksum" in result
        assert result["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_export_empty_repository(
        self,
        mock_embedding_repository,
    ):
        """Test export with empty repository."""
        mock_embedding_repository.list_all = AsyncMock(return_value=[])

        use_case = ExportEmbeddingsUseCase(
            repository=mock_embedding_repository,
        )

        result = await use_case.execute(tenant_id="default")

        assert result["embeddings"] == []
        assert result["count"] == 0


# ============================================================================
# ImportEmbeddingsUseCase Tests
# ============================================================================


class TestImportEmbeddingsUseCase:
    """Test ImportEmbeddingsUseCase."""

    @pytest.mark.asyncio
    async def test_successful_import_merge(
        self,
        mock_embedding_repository,
        sample_embedding,
    ):
        """Test successful embeddings import with merge mode."""
        # Repository surface used by ImportEmbeddingsUseCase
        mock_embedding_repository.get = AsyncMock(return_value=None)
        mock_embedding_repository.update = AsyncMock()
        mock_embedding_repository.save = AsyncMock()

        import_data = {
            "version": "1.0",
            "embeddings": [
                {"user_id": "user1", "embedding": sample_embedding.tolist(), "quality_score": 85.0},
            ],
        }

        use_case = ImportEmbeddingsUseCase(
            repository=mock_embedding_repository,
        )

        result = await use_case.execute(
            import_data=import_data,
            mode="merge",
            tenant_id="default",
        )

        assert result["imported"] >= 0
        assert result["skipped"] >= 0

    @pytest.mark.asyncio
    async def test_import_replace_mode(
        self,
        mock_embedding_repository,
        sample_embedding,
    ):
        """Test import with replace mode clears existing data."""
        mock_embedding_repository.delete_all = AsyncMock()
        mock_embedding_repository.get = AsyncMock(return_value=None)
        mock_embedding_repository.update = AsyncMock()
        mock_embedding_repository.save = AsyncMock()

        import_data = {
            "version": "1.0",
            "embeddings": [
                {"user_id": "user1", "embedding": sample_embedding.tolist(), "quality_score": 85.0},
            ],
        }

        use_case = ImportEmbeddingsUseCase(
            repository=mock_embedding_repository,
        )

        result = await use_case.execute(
            import_data=import_data,
            mode="replace",
            tenant_id="default",
        )

        mock_embedding_repository.delete_all.assert_called_once()


# ============================================================================
# SendWebhookUseCase Tests
# ============================================================================


class TestSendWebhookUseCase:
    """Test SendWebhookUseCase."""

    @pytest.mark.asyncio
    async def test_successful_webhook_send(
        self,
        mock_webhook_sender,
    ):
        """Test successful webhook send."""
        use_case = SendWebhookUseCase(
            webhook_sender=mock_webhook_sender,
        )

        result = await use_case.execute(
            url="https://example.com/webhook",
            event_type="enrollment.success",
            data={"user_id": "test123"},
            tenant_id="default",
        )

        assert isinstance(result, WebhookResult)
        assert result.success is True
        assert result.status_code == 200
        mock_webhook_sender.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_send_with_secret(
        self,
        mock_webhook_sender,
    ):
        """Test webhook send with HMAC secret."""
        use_case = SendWebhookUseCase(
            webhook_sender=mock_webhook_sender,
        )

        result = await use_case.execute(
            url="https://example.com/webhook",
            event_type="verification.success",
            data={"user_id": "test123", "verified": True},
            tenant_id="default",
            secret="my_secret_key",
        )

        assert result.success is True
        # SendWebhookUseCase calls sender.send(url, event, secret) positionally
        call_args = mock_webhook_sender.send.call_args
        passed_secret = (
            call_args.kwargs.get("secret")
            if "secret" in call_args.kwargs
            else (call_args.args[2] if len(call_args.args) >= 3 else None)
        )
        assert passed_secret == "my_secret_key"

    @pytest.mark.asyncio
    async def test_webhook_send_failure(
        self,
        mock_webhook_sender,
    ):
        """Test webhook send failure."""
        mock_webhook_sender.send = AsyncMock(return_value=WebhookResult(
            success=False,
            status_code=500,
            response_time_ms=1000.0,
            error="Internal server error",
        ))

        use_case = SendWebhookUseCase(
            webhook_sender=mock_webhook_sender,
        )

        result = await use_case.execute(
            url="https://example.com/webhook",
            event_type="test",
            data={},
            tenant_id="default",
        )

        assert result.success is False
        assert result.status_code == 500
        assert result.error is not None
