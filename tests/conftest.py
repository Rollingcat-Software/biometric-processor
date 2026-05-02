"""Shared test fixtures and configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest
from cryptography.fernet import Fernet
from PIL import Image

# GDPR P1.3 — repositories now require FIVUCSAS_EMBEDDING_KEY at construction.
# Provide a stable per-test-run key so legacy tests that build the container
# don't fail-fast at import time.
os.environ.setdefault("FIVUCSAS_EMBEDDING_KEY", Fernet.generate_key().decode())

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.verification_result import VerificationResult


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def sample_embedding() -> np.ndarray:
    """Create a sample 128-D face embedding."""
    # Create normalized random embedding
    embedding = np.random.randn(128).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


@pytest.fixture
def sample_embedding_512d() -> np.ndarray:
    """Create a sample 512-D face embedding."""
    embedding = np.random.randn(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


@pytest.fixture
def sample_image() -> np.ndarray:
    """Create a sample image as numpy array."""
    # Create a simple 200x200 RGB image
    return np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)


@pytest.fixture
def sample_face_region() -> np.ndarray:
    """Create a sample face region."""
    # Create a 100x100 face region
    return np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)


@pytest.fixture
def temp_image_file():
    """Create a temporary image file."""
    # Create temp file
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, "test_image.jpg")

    # Create and save a simple image
    img = Image.new("RGB", (200, 200), color=(100, 100, 100))
    img.save(temp_file)

    yield temp_file

    # Cleanup
    try:
        os.remove(temp_file)
        os.rmdir(temp_dir)
    except:
        pass


# ============================================================================
# Domain Entity Fixtures
# ============================================================================


@pytest.fixture
def face_detection_result() -> FaceDetectionResult:
    """Create a sample face detection result."""
    return FaceDetectionResult(
        found=True,
        bounding_box=(50, 50, 100, 100),
        landmarks=None,
        confidence=0.95,
    )


@pytest.fixture
def quality_assessment_good() -> QualityAssessment:
    """Create a good quality assessment."""
    return QualityAssessment(
        score=85.0,
        blur_score=150.0,
        lighting_score=120.0,
        face_size=100,
        is_acceptable=True,
    )


@pytest.fixture
def quality_assessment_poor() -> QualityAssessment:
    """Create a poor quality assessment."""
    return QualityAssessment(
        score=40.0,
        blur_score=50.0,
        lighting_score=60.0,
        face_size=50,
        is_acceptable=False,
    )


@pytest.fixture
def face_embedding_entity(sample_embedding) -> FaceEmbedding:
    """Create a face embedding entity."""
    return FaceEmbedding.create_new(
        user_id="test_user_123",
        vector=sample_embedding,
        quality_score=85.0,
        tenant_id="test_tenant",
    )


@pytest.fixture
def liveness_result_pass() -> LivenessResult:
    """Create a passing liveness result."""
    return LivenessResult(
        is_live=True,
        liveness_score=92.0,
        challenge="smile",
        challenge_completed=True,
    )


@pytest.fixture
def liveness_result_fail() -> LivenessResult:
    """Create a failing liveness result."""
    return LivenessResult(
        is_live=False,
        liveness_score=45.0,
        challenge="smile",
        challenge_completed=False,
    )


@pytest.fixture
def verification_result_match() -> VerificationResult:
    """Create a matching verification result."""
    return VerificationResult(
        verified=True,
        confidence=0.87,
        distance=0.13,
        threshold=0.6,
    )


@pytest.fixture
def verification_result_no_match() -> VerificationResult:
    """Create a non-matching verification result."""
    return VerificationResult(
        verified=False,
        confidence=0.35,
        distance=0.65,
        threshold=0.6,
    )


# ============================================================================
# Mock Infrastructure Fixtures
# ============================================================================


@pytest.fixture
def mock_face_detector(face_detection_result):
    """Create a mock face detector."""
    detector = Mock()
    detector.detect = AsyncMock(return_value=face_detection_result)
    return detector


@pytest.fixture
def mock_embedding_extractor(sample_embedding):
    """Create a mock embedding extractor."""
    extractor = Mock()
    extractor.extract = AsyncMock(return_value=sample_embedding)
    extractor.get_embedding_dimension = Mock(return_value=128)
    return extractor


@pytest.fixture
def mock_quality_assessor(quality_assessment_good):
    """Create a mock quality assessor."""
    assessor = Mock()
    assessor.assess = AsyncMock(return_value=quality_assessment_good)
    assessor.get_minimum_acceptable_score = Mock(return_value=70.0)
    return assessor


@pytest.fixture
def mock_similarity_calculator():
    """Create a mock similarity calculator."""
    calculator = Mock()
    calculator.calculate = Mock(return_value=0.13)  # Low distance = good match
    calculator.get_threshold = Mock(return_value=0.6)
    calculator.get_confidence = Mock(return_value=0.87)
    return calculator


@pytest.fixture
def mock_embedding_repository():
    """Create a mock embedding repository."""
    repository = Mock()
    repository.save = AsyncMock()
    repository.find_by_user_id = AsyncMock(return_value=None)
    repository.find_similar = AsyncMock(return_value=[])
    repository.delete = AsyncMock(return_value=True)
    repository.exists = AsyncMock(return_value=False)
    repository.count = AsyncMock(return_value=0)
    return repository


@pytest.fixture
def mock_file_storage(temp_image_file):
    """Create a mock file storage."""
    storage = Mock()
    storage.save_temp = AsyncMock(return_value=temp_image_file)
    storage.cleanup = AsyncMock()
    storage.read_as_bytes = AsyncMock(return_value=b"fake image data")
    storage.get_storage_path = Mock(return_value="/tmp")
    return storage


@pytest.fixture
def mock_liveness_detector(liveness_result_pass):
    """Create a mock liveness detector."""
    detector = Mock()
    detector.check_liveness = AsyncMock(return_value=liveness_result_pass)
    detector.get_challenge_type = Mock(return_value="smile")
    detector.get_liveness_threshold = Mock(return_value=80.0)
    return detector


# ============================================================================
# Test Utilities
# ============================================================================


@pytest.fixture
def assert_embedding_equal():
    """Utility to assert embeddings are equal."""
    def _assert(emb1: np.ndarray, emb2: np.ndarray, rtol=1e-5):
        assert np.allclose(emb1, emb2, rtol=rtol), "Embeddings not equal"
    return _assert


@pytest.fixture
def create_test_user_id():
    """Factory for creating test user IDs."""
    counter = 0
    def _create(prefix="test_user"):
        nonlocal counter
        counter += 1
        return f"{prefix}_{counter}"
    return _create


# ============================================================================
# Real Image Fixtures (from tests/fixtures/images/)
# ============================================================================


@pytest.fixture
def fixtures_images_path() -> Path:
    """Get the path to test fixture images."""
    return Path(__file__).parent / "fixtures" / "images"


@pytest.fixture
def real_face_images(fixtures_images_path) -> dict:
    """Load real face images from test fixtures.

    Returns:
        Dictionary with user_id as key and list of image paths as value.
    """
    import cv2

    images = {}
    for user_dir in fixtures_images_path.iterdir():
        if user_dir.is_dir():
            user_images = []
            for img_path in user_dir.glob("*"):
                if img_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                    img = cv2.imread(str(img_path))
                    if img is not None:
                        user_images.append({
                            "path": str(img_path),
                            "image": img,
                            "name": img_path.name,
                        })
            if user_images:
                images[user_dir.name] = user_images
    return images


@pytest.fixture
def sample_real_image(real_face_images) -> np.ndarray:
    """Get a single real face image for testing."""
    for user_id, images in real_face_images.items():
        if images:
            return images[0]["image"]
    # Fallback to random image
    return np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)


# ============================================================================
# Performance Optimization Fixtures
# ============================================================================


@pytest.fixture
def thread_pool_manager():
    """Create a thread pool manager for tests."""
    from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
    pool = ThreadPoolManager(max_workers=2, thread_name_prefix="test-pool")
    yield pool
    pool.shutdown(wait=True)


@pytest.fixture
def embedding_cache():
    """Create an embedding cache for tests."""
    from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache
    return ThreadSafeLRUCache[str, np.ndarray](max_size=100, ttl_seconds=300)


@pytest.fixture
def thread_safe_repository():
    """Create a thread-safe repository for tests."""
    from app.infrastructure.persistence.repositories.thread_safe_memory_repository import (
        ThreadSafeInMemoryEmbeddingRepository,
    )
    return ThreadSafeInMemoryEmbeddingRepository(max_capacity=100)


@pytest.fixture
def auto_cleaning_storage():
    """Create auto-cleaning rate limit storage for tests."""
    from app.infrastructure.rate_limit.auto_cleaning_memory_storage import (
        AutoCleaningMemoryStorage,
    )
    return AutoCleaningMemoryStorage(max_entries=100, cleanup_interval_seconds=60)
