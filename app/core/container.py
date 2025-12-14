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
from app.application.use_cases.detect_card_type import DetectCardTypeUseCase

# Application use cases
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.application.use_cases.search_face import SearchFaceUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase

# New feature use cases
from app.application.use_cases.analyze_quality import AnalyzeQualityUseCase
from app.application.use_cases.detect_multi_face import DetectMultiFaceUseCase
from app.application.use_cases.analyze_demographics import AnalyzeDemographicsUseCase
from app.application.use_cases.detect_landmarks import DetectLandmarksUseCase
from app.application.use_cases.compare_faces import CompareFacesUseCase
from app.application.use_cases.compute_similarity_matrix import ComputeSimilarityMatrixUseCase
from app.application.use_cases.export_embeddings import ExportEmbeddingsUseCase
from app.application.use_cases.import_embeddings import ImportEmbeddingsUseCase
from app.application.use_cases.send_webhook import SendWebhookUseCase
from app.core.config import settings
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.event_bus import IEventBus

# Domain interfaces (imported for type hints)
from app.domain.interfaces.card_type_detector import ICardTypeDetector
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.file_storage import IFileStorage
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

# Infrastructure implementations
from app.infrastructure.ml.factories.detector_factory import FaceDetectorFactory
from app.infrastructure.ml.factories.extractor_factory import EmbeddingExtractorFactory
from app.infrastructure.ml.factories.liveness_factory import LivenessDetectorFactory
from app.infrastructure.ml.factories.similarity_factory import SimilarityCalculatorFactory
<<<<<<< Updated upstream
from app.infrastructure.ml.factories.demographics_factory import DemographicsAnalyzerFactory
from app.infrastructure.ml.factories.landmark_factory import LandmarkDetectorFactory
from app.infrastructure.ml.factories.preprocessor_factory import ImagePreprocessorFactory
from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory
from app.infrastructure.rate_limit.storage_factory import RateLimitStorageFactory
from app.infrastructure.ml.card_type.yolo_card_type_detector import YOLOCardTypeDetector

# New domain interfaces
from app.domain.interfaces.demographics_analyzer import IDemographicsAnalyzer
from app.domain.interfaces.landmark_detector import ILandmarkDetector
from app.domain.interfaces.image_preprocessor import IImagePreprocessor
from app.domain.interfaces.webhook_sender import IWebhookSender
from app.domain.interfaces.rate_limit_storage import IRateLimitStorage
=======
from app.infrastructure.ml.liveness.enhanced_liveness_detector import EnhancedLivenessDetector
>>>>>>> Stashed changes
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
        Liveness detector implementation based on LIVENESS_MODE setting:
        - passive: Texture-based analysis (printed photos, screens)
        - active: Facial action analysis (smile, blink)
        - combined: Both methods for highest accuracy

<<<<<<< Updated upstream
    Uses LivenessDetectorFactory for Open/Closed Principle compliance.
    """
    logger.info(f"Creating liveness detector: {settings.LIVENESS_MODE}")
    return LivenessDetectorFactory.create(
        mode=settings.LIVENESS_MODE,
        liveness_threshold=settings.LIVENESS_THRESHOLD,
    )


@lru_cache()
def get_card_type_detector() -> ICardTypeDetector:
    """Get card type detector instance (singleton).

    Returns:
        Card type detector implementation
    """
    logger.info("Creating card type detector (YOLO)")
    return YOLOCardTypeDetector(
        confidence_threshold=0.5,
    )


@lru_cache()
def get_demographics_analyzer() -> IDemographicsAnalyzer:
    """Get demographics analyzer instance (singleton).

    Returns:
        Demographics analyzer implementation
    """
    logger.info("Creating demographics analyzer")
    return DemographicsAnalyzerFactory.create(
        backend="deepface",
        include_race=settings.DEMOGRAPHICS_INCLUDE_RACE,
        include_emotion=settings.DEMOGRAPHICS_INCLUDE_EMOTION,
    )


@lru_cache()
def get_landmark_detector() -> ILandmarkDetector:
    """Get landmark detector instance (singleton).

    Returns:
        Landmark detector implementation
    """
    logger.info(f"Creating landmark detector: {settings.LANDMARK_MODEL}")
    return LandmarkDetectorFactory.create(
        model=settings.LANDMARK_MODEL,
    )


@lru_cache()
def get_image_preprocessor() -> IImagePreprocessor:
    """Get image preprocessor instance (singleton).

    Returns:
        Image preprocessor implementation
    """
    logger.info("Creating image preprocessor")
    return ImagePreprocessorFactory.create(
        preprocessor_type="opencv",
        auto_rotate=settings.PREPROCESS_AUTO_ROTATE,
        max_size=settings.PREPROCESS_MAX_SIZE,
        normalize=settings.PREPROCESS_NORMALIZE,
    )


@lru_cache()
def get_webhook_sender() -> IWebhookSender:
    """Get webhook sender instance (singleton).

    Returns:
        Webhook sender implementation
    """
    logger.info("Creating webhook sender")
    return WebhookSenderFactory.create(
        sender_type="http",
        retry_count=settings.WEBHOOK_RETRY_COUNT,
    )


@lru_cache()
def get_rate_limit_storage() -> IRateLimitStorage:
    """Get rate limit storage instance (singleton).

    Returns:
        Rate limit storage implementation
    """
    logger.info(f"Creating rate limit storage: {settings.RATE_LIMIT_STORAGE}")
    return RateLimitStorageFactory.create(
        storage_type=settings.RATE_LIMIT_STORAGE,
=======
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
>>>>>>> Stashed changes
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


def get_detect_card_type_use_case() -> DetectCardTypeUseCase:
    """Get detect card type use case instance.

    Returns:
        DetectCardTypeUseCase with all dependencies injected
    """
    return DetectCardTypeUseCase(
        detector=get_card_type_detector(),
    )


def get_analyze_quality_use_case() -> AnalyzeQualityUseCase:
    """Get analyze quality use case instance.

    Returns:
        AnalyzeQualityUseCase with all dependencies injected
    """
    return AnalyzeQualityUseCase(
        detector=get_face_detector(),
        quality_assessor=get_quality_assessor(),
    )


def get_detect_multi_face_use_case() -> DetectMultiFaceUseCase:
    """Get detect multi face use case instance.

    Returns:
        DetectMultiFaceUseCase with all dependencies injected
    """
    return DetectMultiFaceUseCase(
        detector=get_face_detector(),
        quality_assessor=get_quality_assessor(),
    )


def get_analyze_demographics_use_case() -> AnalyzeDemographicsUseCase:
    """Get analyze demographics use case instance.

    Returns:
        AnalyzeDemographicsUseCase with all dependencies injected
    """
    return AnalyzeDemographicsUseCase(
        detector=get_face_detector(),
        demographics_analyzer=get_demographics_analyzer(),
    )


def get_detect_landmarks_use_case() -> DetectLandmarksUseCase:
    """Get detect landmarks use case instance.

    Returns:
        DetectLandmarksUseCase with all dependencies injected
    """
    return DetectLandmarksUseCase(
        detector=get_face_detector(),
        landmark_detector=get_landmark_detector(),
    )


def get_compare_faces_use_case() -> CompareFacesUseCase:
    """Get compare faces use case instance.

    Returns:
        CompareFacesUseCase with all dependencies injected
    """
    return CompareFacesUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        similarity_calculator=get_similarity_calculator(),
        quality_assessor=get_quality_assessor(),
    )


def get_compute_similarity_matrix_use_case() -> ComputeSimilarityMatrixUseCase:
    """Get compute similarity matrix use case instance.

    Returns:
        ComputeSimilarityMatrixUseCase with all dependencies injected
    """
    return ComputeSimilarityMatrixUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        similarity_calculator=get_similarity_calculator(),
    )


def get_export_embeddings_use_case() -> ExportEmbeddingsUseCase:
    """Get export embeddings use case instance.

    Returns:
        ExportEmbeddingsUseCase with all dependencies injected
    """
    return ExportEmbeddingsUseCase(
        repository=get_embedding_repository(),
    )


def get_import_embeddings_use_case() -> ImportEmbeddingsUseCase:
    """Get import embeddings use case instance.

    Returns:
        ImportEmbeddingsUseCase with all dependencies injected
    """
    return ImportEmbeddingsUseCase(
        repository=get_embedding_repository(),
    )


def get_send_webhook_use_case() -> SendWebhookUseCase:
    """Get send webhook use case instance.

    Returns:
        SendWebhookUseCase with all dependencies injected
    """
    return SendWebhookUseCase(
        webhook_sender=get_webhook_sender(),
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
<<<<<<< Updated upstream
    get_card_type_detector.cache_clear()
    get_demographics_analyzer.cache_clear()
    get_landmark_detector.cache_clear()
    get_image_preprocessor.cache_clear()
    get_webhook_sender.cache_clear()
    get_rate_limit_storage.cache_clear()
=======
    get_event_bus.cache_clear()
    get_event_handler.cache_clear()
    get_event_router.cache_clear()
    get_event_publisher.cache_clear()
>>>>>>> Stashed changes
