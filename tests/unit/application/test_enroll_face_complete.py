"""
Comprehensive unit tests for EnrollFace use case.

Tests all scenarios:
- Successful enrollment
- No face detected
- Multiple faces detected
- Poor quality image
- Liveness check failed
- Duplicate user
- Storage errors
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import numpy as np

from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.domain.entities.face_detection import FaceDetection
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.exceptions.face_errors import (
    NoFaceDetectedError,
    MultipleFacesDetectedError,
    PoorQualityImageError
)
from app.domain.exceptions.liveness_errors import LivenessCheckFailedError
from app.domain.exceptions.repository_errors import DuplicateUserError
from app.domain.exceptions.storage_errors import StorageError


@pytest.fixture
def mock_detector():
    """Mock face detector."""
    detector = AsyncMock()
    return detector


@pytest.fixture
def mock_extractor():
    """Mock embedding extractor."""
    extractor = AsyncMock()
    return extractor


@pytest.fixture
def mock_liveness_detector():
    """Mock liveness detector."""
    liveness = AsyncMock()
    return liveness


@pytest.fixture
def mock_quality_assessor():
    """Mock quality assessor."""
    assessor = AsyncMock()
    return assessor


@pytest.fixture
def mock_repository():
    """Mock embedding repository."""
    repository = AsyncMock()
    return repository


@pytest.fixture
def mock_storage():
    """Mock file storage."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def use_case(
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_repository,
    mock_storage
):
    """Create EnrollFaceUseCase with all mocks."""
    return EnrollFaceUseCase(
        detector=mock_detector,
        extractor=mock_extractor,
        liveness_detector=mock_liveness_detector,
        quality_assessor=mock_quality_assessor,
        repository=mock_repository,
        storage=mock_storage
    )


@pytest.fixture
def valid_image_data():
    """Valid base64 encoded image data."""
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def valid_face_detection():
    """Valid face detection result."""
    return FaceDetection(
        confidence=0.99,
        bounding_box=(100, 100, 200, 200),
        landmarks={
            "left_eye": (120, 140),
            "right_eye": (180, 140),
            "nose": (150, 160),
            "left_mouth": (130, 180),
            "right_mouth": (170, 180)
        }
    )


@pytest.fixture
def valid_embedding():
    """Valid face embedding."""
    return FaceEmbedding(
        vector=np.random.rand(512).tolist(),
        model="VGG-Face",
        version="1.0"
    )


@pytest.fixture
def valid_liveness_result():
    """Valid liveness check result (real face)."""
    return LivenessResult(
        is_live=True,
        confidence=0.95,
        checks={
            "texture": 0.96,
            "frequency": 0.94,
            "depth": 0.95
        }
    )


@pytest.fixture
def valid_quality_assessment():
    """Valid quality assessment (passes threshold)."""
    return QualityAssessment(
        overall_score=0.85,
        brightness=0.80,
        sharpness=0.90,
        contrast=0.85,
        passes_threshold=True
    )


# ============== SUCCESS TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_success(
    use_case,
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_repository,
    mock_storage,
    valid_image_data,
    valid_face_detection,
    valid_embedding,
    valid_liveness_result,
    valid_quality_assessment
):
    """Test successful face enrollment."""
    # Arrange
    user_id = "test-user-123"

    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = valid_quality_assessment
    mock_liveness_detector.detect_liveness.return_value = valid_liveness_result
    mock_extractor.extract.return_value = valid_embedding
    mock_storage.save.return_value = "path/to/image.jpg"
    mock_repository.store_embedding.return_value = None

    # Act
    result = await use_case.execute(user_id, valid_image_data)

    # Assert
    assert result is not None
    assert result["user_id"] == user_id
    assert result["enrolled"] is True
    assert "embedding_id" in result
    assert result["quality_score"] == 0.85
    assert result["liveness_score"] == 0.95

    # Verify all services were called
    mock_detector.detect.assert_called_once()
    mock_quality_assessor.assess.assert_called_once()
    mock_liveness_detector.detect_liveness.assert_called_once()
    mock_extractor.extract.assert_called_once()
    mock_storage.save.assert_called_once()
    mock_repository.store_embedding.assert_called_once()


@pytest.mark.asyncio
async def test_enroll_face_stores_correct_embedding_data(
    use_case,
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_repository,
    mock_storage,
    valid_image_data,
    valid_face_detection,
    valid_embedding,
    valid_liveness_result,
    valid_quality_assessment
):
    """Test that enrollment stores correct embedding data."""
    # Arrange
    user_id = "test-user-123"

    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = valid_quality_assessment
    mock_liveness_detector.detect_liveness.return_value = valid_liveness_result
    mock_extractor.extract.return_value = valid_embedding
    mock_storage.save.return_value = "path/to/image.jpg"

    # Act
    await use_case.execute(user_id, valid_image_data)

    # Assert - Check repository was called with correct parameters
    call_args = mock_repository.store_embedding.call_args
    assert call_args is not None
    stored_user_id = call_args[0][0]
    stored_embedding = call_args[0][1]

    assert stored_user_id == user_id
    assert len(stored_embedding.vector) == 512


# ============== NO FACE DETECTED TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_no_face_detected(
    use_case,
    mock_detector,
    valid_image_data
):
    """Test enrollment fails when no face is detected."""
    # Arrange
    user_id = "test-user-123"
    mock_detector.detect.return_value = []  # No faces detected

    # Act & Assert
    with pytest.raises(NoFaceDetectedError) as exc_info:
        await use_case.execute(user_id, valid_image_data)

    assert "No face detected" in str(exc_info.value)


# ============== MULTIPLE FACES DETECTED TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_multiple_faces_detected(
    use_case,
    mock_detector,
    valid_image_data,
    valid_face_detection
):
    """Test enrollment fails when multiple faces are detected."""
    # Arrange
    user_id = "test-user-123"
    face2 = FaceDetection(
        confidence=0.95,
        bounding_box=(300, 100, 400, 200),
        landmarks={}
    )
    mock_detector.detect.return_value = [valid_face_detection, face2]

    # Act & Assert
    with pytest.raises(MultipleFacesDetectedError) as exc_info:
        await use_case.execute(user_id, valid_image_data)

    assert "Multiple faces detected" in str(exc_info.value)
    assert "2" in str(exc_info.value)


# ============== POOR QUALITY TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_poor_quality_image(
    use_case,
    mock_detector,
    mock_quality_assessor,
    valid_image_data,
    valid_face_detection
):
    """Test enrollment fails when image quality is too low."""
    # Arrange
    user_id = "test-user-123"
    mock_detector.detect.return_value = [valid_face_detection]

    poor_quality = QualityAssessment(
        overall_score=0.40,
        brightness=0.30,
        sharpness=0.40,
        contrast=0.50,
        passes_threshold=False
    )
    mock_quality_assessor.assess.return_value = poor_quality

    # Act & Assert
    with pytest.raises(PoorQualityImageError) as exc_info:
        await use_case.execute(user_id, valid_image_data)

    assert "Poor quality" in str(exc_info.value)


@pytest.mark.asyncio
async def test_enroll_face_low_brightness(
    use_case,
    mock_detector,
    mock_quality_assessor,
    valid_image_data,
    valid_face_detection
):
    """Test enrollment fails when brightness is too low."""
    # Arrange
    user_id = "test-user-123"
    mock_detector.detect.return_value = [valid_face_detection]

    low_brightness = QualityAssessment(
        overall_score=0.45,
        brightness=0.20,  # Very low
        sharpness=0.80,
        contrast=0.70,
        passes_threshold=False
    )
    mock_quality_assessor.assess.return_value = low_brightness

    # Act & Assert
    with pytest.raises(PoorQualityImageError):
        await use_case.execute(user_id, valid_image_data)


# ============== LIVENESS CHECK FAILED TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_liveness_check_failed(
    use_case,
    mock_detector,
    mock_quality_assessor,
    mock_liveness_detector,
    valid_image_data,
    valid_face_detection,
    valid_quality_assessment
):
    """Test enrollment fails when liveness check fails."""
    # Arrange
    user_id = "test-user-123"
    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = valid_quality_assessment

    fake_face_result = LivenessResult(
        is_live=False,
        confidence=0.85,
        checks={
            "texture": 0.40,  # Low texture score indicates fake
            "frequency": 0.35,
            "depth": 0.30
        }
    )
    mock_liveness_detector.detect_liveness.return_value = fake_face_result

    # Act & Assert
    with pytest.raises(LivenessCheckFailedError) as exc_info:
        await use_case.execute(user_id, valid_image_data)

    assert "Liveness check failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_enroll_face_low_liveness_confidence(
    use_case,
    mock_detector,
    mock_quality_assessor,
    mock_liveness_detector,
    valid_image_data,
    valid_face_detection,
    valid_quality_assessment
):
    """Test enrollment fails when liveness confidence is too low."""
    # Arrange
    user_id = "test-user-123"
    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = valid_quality_assessment

    low_confidence_result = LivenessResult(
        is_live=False,
        confidence=0.30,  # Very low confidence
        checks={"texture": 0.30, "frequency": 0.30, "depth": 0.30}
    )
    mock_liveness_detector.detect_liveness.return_value = low_confidence_result

    # Act & Assert
    with pytest.raises(LivenessCheckFailedError):
        await use_case.execute(user_id, valid_image_data)


# ============== DUPLICATE USER TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_duplicate_user(
    use_case,
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_repository,
    mock_storage,
    valid_image_data,
    valid_face_detection,
    valid_embedding,
    valid_liveness_result,
    valid_quality_assessment
):
    """Test enrollment fails when user is already enrolled."""
    # Arrange
    user_id = "test-user-123"

    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = valid_quality_assessment
    mock_liveness_detector.detect_liveness.return_value = valid_liveness_result
    mock_extractor.extract.return_value = valid_embedding
    mock_storage.save.return_value = "path/to/image.jpg"
    mock_repository.store_embedding.side_effect = DuplicateUserError(user_id)

    # Act & Assert
    with pytest.raises(DuplicateUserError) as exc_info:
        await use_case.execute(user_id, valid_image_data)

    assert user_id in str(exc_info.value)


# ============== STORAGE ERROR TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_storage_error(
    use_case,
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_storage,
    valid_image_data,
    valid_face_detection,
    valid_embedding,
    valid_liveness_result,
    valid_quality_assessment
):
    """Test enrollment fails when storage operation fails."""
    # Arrange
    user_id = "test-user-123"

    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = valid_quality_assessment
    mock_liveness_detector.detect_liveness.return_value = valid_liveness_result
    mock_extractor.extract.return_value = valid_embedding
    mock_storage.save.side_effect = StorageError("Disk full")

    # Act & Assert
    with pytest.raises(StorageError) as exc_info:
        await use_case.execute(user_id, valid_image_data)

    assert "Disk full" in str(exc_info.value)


# ============== INPUT VALIDATION TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_invalid_user_id(use_case):
    """Test enrollment fails with invalid user ID."""
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await use_case.execute("", "some-image-data")

    assert "user_id" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_enroll_face_null_user_id(use_case):
    """Test enrollment fails with null user ID."""
    # Act & Assert
    with pytest.raises(ValueError):
        await use_case.execute(None, "some-image-data")


@pytest.mark.asyncio
async def test_enroll_face_invalid_image_data(use_case):
    """Test enrollment fails with invalid image data."""
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await use_case.execute("user-123", "")

    assert "image" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_enroll_face_null_image_data(use_case):
    """Test enrollment fails with null image data."""
    # Act & Assert
    with pytest.raises(ValueError):
        await use_case.execute("user-123", None)


# ============== EDGE CASE TESTS ==============

@pytest.mark.asyncio
async def test_enroll_face_very_high_quality(
    use_case,
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_repository,
    mock_storage,
    valid_image_data,
    valid_face_detection,
    valid_embedding,
    valid_liveness_result
):
    """Test enrollment with very high quality image."""
    # Arrange
    user_id = "test-user-123"

    perfect_quality = QualityAssessment(
        overall_score=0.99,
        brightness=0.99,
        sharpness=0.99,
        contrast=0.99,
        passes_threshold=True
    )

    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = perfect_quality
    mock_liveness_detector.detect_liveness.return_value = valid_liveness_result
    mock_extractor.extract.return_value = valid_embedding
    mock_storage.save.return_value = "path/to/image.jpg"

    # Act
    result = await use_case.execute(user_id, valid_image_data)

    # Assert
    assert result["quality_score"] == 0.99


@pytest.mark.asyncio
async def test_enroll_face_borderline_quality(
    use_case,
    mock_detector,
    mock_extractor,
    mock_liveness_detector,
    mock_quality_assessor,
    mock_repository,
    mock_storage,
    valid_image_data,
    valid_face_detection,
    valid_embedding,
    valid_liveness_result
):
    """Test enrollment with borderline quality (just above threshold)."""
    # Arrange
    user_id = "test-user-123"

    borderline_quality = QualityAssessment(
        overall_score=0.51,  # Just above 0.5 threshold
        brightness=0.51,
        sharpness=0.51,
        contrast=0.51,
        passes_threshold=True
    )

    mock_detector.detect.return_value = [valid_face_detection]
    mock_quality_assessor.assess.return_value = borderline_quality
    mock_liveness_detector.detect_liveness.return_value = valid_liveness_result
    mock_extractor.extract.return_value = valid_embedding
    mock_storage.save.return_value = "path/to/image.jpg"

    # Act
    result = await use_case.execute(user_id, valid_image_data)

    # Assert - Should still succeed
    assert result["enrolled"] is True
    assert result["quality_score"] == 0.51
