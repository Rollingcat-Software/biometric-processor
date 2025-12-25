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

from app.application.services.event_publisher import EventPublisher
from app.application.use_cases.batch_process import BatchEnrollmentUseCase, BatchVerificationUseCase
from app.application.use_cases.check_liveness import CheckLivenessUseCase

# Application use cases
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.application.use_cases.search_face import SearchFaceUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.core.config import settings
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.event_bus import IEventBus

# Domain interfaces (imported for type hints)
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.file_storage import IFileStorage
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

# Infrastructure implementations
from app.infrastructure.ml.factories.detector_factory import FaceDetectorFactory
from app.infrastructure.ml.factories.extractor_factory import EmbeddingExtractorFactory
from app.infrastructure.ml.factories.similarity_factory import SimilarityCalculatorFactory
from app.infrastructure.ml.liveness.enhanced_liveness_detector import EnhancedLivenessDetector
from app.infrastructure.ml.quality.quality_assessor import QualityAssessor
from app.infrastructure.messaging.event_handlers import BiometricEventHandler, EventRouter
from app.infrastructure.messaging.redis_event_bus import RedisEventBus
from app.infrastructure.persistence.repositories.memory_embedding_repository import (
    InMemoryEmbeddingRepository,
)
from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
    PgVectorEmbeddingRepository,
)
from app.infrastructure.storage.local_file_storage import LocalFileStorage

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
    return FaceDetectorFactory.create(detector_type=settings.FACE_DETECTION_BACKEND, align=True)


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
        Embedding repository implementation based on configuration

    Note:
        - If USE_PGVECTOR=True: Returns PgVectorEmbeddingRepository (production)
        - If USE_PGVECTOR=False: Returns InMemoryEmbeddingRepository (development/testing)

        Set USE_PGVECTOR environment variable to control which implementation is used.
    """
    if settings.USE_PGVECTOR:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set when USE_PGVECTOR=True")

        logger.info(
            f"Creating embedding repository (pgvector) - "
            f"dimension={settings.EMBEDDING_DIMENSION}"
        )
        return PgVectorEmbeddingRepository(
            database_url=settings.DATABASE_URL,
            pool_min_size=settings.DATABASE_POOL_MIN_SIZE,
            pool_max_size=settings.DATABASE_POOL_MAX_SIZE,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
        )
    else:
        logger.info("Creating embedding repository (in-memory)")
        return InMemoryEmbeddingRepository()


@lru_cache()
def get_liveness_detector() -> ILivenessDetector:
    """Get liveness detector instance (singleton).

    Returns:
        Liveness detector implementation

    Note:
        Uses EnhancedLivenessDetector which combines multiple techniques:
        - Texture analysis (LBP) to detect print attacks
        - Blink detection using eye aspect ratio
        - Smile detection using mouth aspect ratio
        - Color/frequency analysis for screen detection
    """
    logger.info("Creating liveness detector (enhanced multi-modal)")
    return EnhancedLivenessDetector(
        texture_threshold=100.0,
        liveness_threshold=70.0,
        enable_blink_detection=True,
        enable_smile_detection=True,
        blink_frames_required=2,
    )


@lru_cache()
def get_event_bus() -> IEventBus:
    """Get event bus instance (singleton).

    Returns:
        Event bus implementation (Redis-based)

    Note:
        - Uses Redis Pub/Sub for real-time event distribution
        - Async/non-blocking operations
        - Automatic reconnection handling
        - Configurable via environment variables
    """
    if not settings.EVENT_BUS_ENABLED:
        logger.warning("Event bus is disabled in configuration")
        # Return a null/no-op implementation if needed
        # For now, we'll still create it but won't use it

    logger.info(f"Creating Redis event bus: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    return RedisEventBus(
        redis_url=settings.redis_url,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        retry_attempts=settings.EVENT_BUS_RETRY_ATTEMPTS,
        retry_delay=settings.EVENT_BUS_RETRY_DELAY,
    )


@lru_cache()
def get_event_handler() -> BiometricEventHandler:
    """Get event handler instance (singleton).

    Returns:
        Biometric event handler for processing incoming events
    """
    logger.info("Creating biometric event handler")
    return BiometricEventHandler()


@lru_cache()
def get_event_router() -> EventRouter:
    """Get event router instance (singleton).

    Returns:
        Event router for dispatching events to handlers
    """
    logger.info("Creating event router")
    return EventRouter(handler=get_event_handler())


@lru_cache()
def get_event_publisher() -> EventPublisher:
    """Get event publisher instance (singleton).

    Returns:
        Event publisher for use cases to publish events

    Note:
        Returns publisher with or without event bus depending on configuration
    """
    if settings.EVENT_BUS_ENABLED:
        logger.info("Creating event publisher (enabled)")
        return EventPublisher(event_bus=get_event_bus())
    else:
        logger.info("Creating event publisher (disabled)")
        return EventPublisher(event_bus=None)


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


def get_search_face_use_case() -> SearchFaceUseCase:
    """Get search face use case instance.

    Returns:
        SearchFaceUseCase with all dependencies injected
    """
    return SearchFaceUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        repository=get_embedding_repository(),
        similarity_calculator=get_similarity_calculator(),
    )


def get_batch_enrollment_use_case() -> BatchEnrollmentUseCase:
    """Get batch enrollment use case instance.

    Returns:
        BatchEnrollmentUseCase with all dependencies injected
    """
    return BatchEnrollmentUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        quality_assessor=get_quality_assessor(),
        repository=get_embedding_repository(),
        max_concurrent=5,
    )


def get_batch_verification_use_case() -> BatchVerificationUseCase:
    """Get batch verification use case instance.

    Returns:
        BatchVerificationUseCase with all dependencies injected
    """
    return BatchVerificationUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        repository=get_embedding_repository(),
        similarity_calculator=get_similarity_calculator(),
        max_concurrent=5,
        default_threshold=settings.VERIFICATION_THRESHOLD,
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

    # Initialize event bus and handlers (if enabled)
    if settings.EVENT_BUS_ENABLED:
        get_event_bus()
        get_event_handler()
        get_event_router()
        get_event_publisher()

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
    get_event_bus.cache_clear()
    get_event_handler.cache_clear()
    get_event_router.cache_clear()
    get_event_publisher.cache_clear()
