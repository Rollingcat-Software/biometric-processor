"""Dependency injection container.

This module provides factory functions for creating and wiring up
all application dependencies.

Following Dependency Inversion Principle:
- High-level modules (use cases) depend on abstractions (interfaces)
- Low-level modules (infrastructure) implement abstractions
- This container wires them together
"""

import logging
from functools import lru_cache

from app.core.config import settings

# Domain interfaces (imported for type hints)
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.file_storage import IFileStorage
from app.domain.interfaces.liveness_detector import ILivenessDetector

# Infrastructure implementations
from app.infrastructure.ml.factories.detector_factory import FaceDetectorFactory
from app.infrastructure.ml.factories.extractor_factory import (
    EmbeddingExtractorFactory,
)
from app.infrastructure.ml.factories.similarity_factory import (
    SimilarityCalculatorFactory,
)
from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
from app.infrastructure.ml.liveness.stub_liveness_detector import StubLivenessDetector
from app.infrastructure.storage.local_file_storage import LocalFileStorage
from app.infrastructure.persistence.repositories.memory_embedding_repository import (
    InMemoryEmbeddingRepository,
)

# Application use cases
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.application.use_cases.check_liveness import CheckLivenessUseCase

logger = logging.getLogger(__name__)


# ============================================================================
# Infrastructure Layer Dependencies (Singletons)
# ============================================================================


@lru_cache()
def get_face_detector() -> IFaceDetector:
    """Get face detector instance (singleton).

    Returns:
        Face detector implementation
    """
    logger.info(f"Creating face detector: {settings.FACE_DETECTION_BACKEND}")
    return FaceDetectorFactory.create(
        detector_type=settings.FACE_DETECTION_BACKEND, align=True
    )


@lru_cache()
def get_embedding_extractor() -> IEmbeddingExtractor:
    """Get embedding extractor instance (singleton).

    Returns:
        Embedding extractor implementation
    """
    logger.info(f"Creating embedding extractor: {settings.FACE_RECOGNITION_MODEL}")
    return EmbeddingExtractorFactory.create(
        model_name=settings.FACE_RECOGNITION_MODEL,
        detector_backend=settings.FACE_DETECTION_BACKEND,
        enforce_detection=False,
    )


@lru_cache()
def get_quality_assessor() -> IQualityAssessor:
    """Get quality assessor instance (singleton).

    Returns:
        Quality assessor implementation
    """
    logger.info("Creating quality assessor")
    return QualityAssessor(
        blur_threshold=settings.BLUR_THRESHOLD,
        min_face_size=settings.MIN_FACE_SIZE,
        quality_threshold=settings.QUALITY_THRESHOLD,
    )


@lru_cache()
def get_similarity_calculator() -> ISimilarityCalculator:
    """Get similarity calculator instance (singleton).

    Returns:
        Similarity calculator implementation
    """
    logger.info("Creating similarity calculator")
    return SimilarityCalculatorFactory.create(
        metric="cosine", threshold=settings.VERIFICATION_THRESHOLD
    )


@lru_cache()
def get_file_storage() -> IFileStorage:
    """Get file storage instance (singleton).

    Returns:
        File storage implementation
    """
    logger.info(f"Creating file storage: {settings.UPLOAD_FOLDER}")
    return LocalFileStorage(storage_path=settings.UPLOAD_FOLDER)


@lru_cache()
def get_embedding_repository() -> IEmbeddingRepository:
    """Get embedding repository instance (singleton).

    Returns:
        Embedding repository implementation

    Note:
        Currently returns InMemoryEmbeddingRepository for MVP.
        Will be replaced with PostgreSQL repository in Sprint 4.
    """
    logger.info("Creating embedding repository (in-memory)")
    return InMemoryEmbeddingRepository()


@lru_cache()
def get_liveness_detector() -> ILivenessDetector:
    """Get liveness detector instance (singleton).

    Returns:
        Liveness detector implementation

    Note:
        Currently returns StubLivenessDetector for MVP.
        Will be replaced with real smile detector in Sprint 3.
    """
    logger.info("Creating liveness detector (stub)")
    return StubLivenessDetector(default_score=85.0)


# ============================================================================
# Application Layer Dependencies (Use Cases)
# ============================================================================


def get_enroll_face_use_case() -> EnrollFaceUseCase:
    """Get enroll face use case instance.

    Returns:
        EnrollFaceUseCase with all dependencies injected
    """
    return EnrollFaceUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        quality_assessor=get_quality_assessor(),
        repository=get_embedding_repository(),
    )


def get_verify_face_use_case() -> VerifyFaceUseCase:
    """Get verify face use case instance.

    Returns:
        VerifyFaceUseCase with all dependencies injected
    """
    return VerifyFaceUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        similarity_calculator=get_similarity_calculator(),
        repository=get_embedding_repository(),
    )


def get_check_liveness_use_case() -> CheckLivenessUseCase:
    """Get check liveness use case instance.

    Returns:
        CheckLivenessUseCase with all dependencies injected
    """
    return CheckLivenessUseCase(
        detector=get_face_detector(),
        liveness_detector=get_liveness_detector(),
    )


# ============================================================================
# Utility Functions
# ============================================================================


def initialize_dependencies() -> None:
    """Initialize all singleton dependencies.

    This pre-loads ML models at application startup for better
    first-request performance.
    """
    logger.info("Initializing dependencies...")

    # Pre-load expensive ML models
    get_face_detector()
    get_embedding_extractor()
    get_quality_assessor()
    get_similarity_calculator()

    # Initialize storage
    get_file_storage()
    get_embedding_repository()
    get_liveness_detector()

    logger.info("Dependencies initialized successfully")


def clear_cache() -> None:
    """Clear dependency cache (for testing).

    Warning:
        This will cause all dependencies to be recreated.
        Only use in tests or during development.
    """
    logger.warning("Clearing dependency cache")

    get_face_detector.cache_clear()
    get_embedding_extractor.cache_clear()
    get_quality_assessor.cache_clear()
    get_similarity_calculator.cache_clear()
    get_file_storage.cache_clear()
    get_embedding_repository.cache_clear()
    get_liveness_detector.cache_clear()
