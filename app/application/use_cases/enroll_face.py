"""Face enrollment use case."""

import logging
from typing import Optional

import cv2
import numpy as np

from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.exceptions.face_errors import PoorImageQualityError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor

logger = logging.getLogger(__name__)


class EnrollFaceUseCase:
    """Use case for enrolling a user's face.

    This use case orchestrates the following steps:
    1. Detect face in image
    2. Extract face region
    3. Assess quality
    4. Extract embedding
    5. Save to repository

    Following Single Responsibility Principle: Only handles enrollment orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        quality_assessor: IQualityAssessor,
        repository: IEmbeddingRepository,
    ) -> None:
        """Initialize enrollment use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            quality_assessor: Quality assessor implementation
            repository: Embedding repository implementation
        """
        self._detector = detector
        self._extractor = extractor
        self._quality_assessor = quality_assessor
        self._repository = repository

        logger.info("EnrollFaceUseCase initialized")

    async def execute(
        self,
        user_id: str,
        image_path: str,
        tenant_id: Optional[str] = None,
    ) -> FaceEmbedding:
        """Execute face enrollment.

        Args:
            user_id: Unique identifier for the user
            image_path: Path to image file
            tenant_id: Optional tenant identifier for multi-tenancy

        Returns:
            FaceEmbedding entity with enrollment result

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            PoorImageQualityError: When quality is below threshold
            EmbeddingExtractionError: When embedding extraction fails
            RepositoryError: When save to repository fails
        """
        logger.info(f"Starting face enrollment for user_id={user_id}, tenant_id={tenant_id}")

        # Initialize image variables for cleanup in finally block
        image = None
        face_region = None

        try:
            # Step 1: Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to load image: {image_path}")

            # Step 2: Detect face
            logger.debug("Step 1/4: Detecting face...")
            detection = await self._detector.detect(image)

            # Step 3: Extract face region using bounding box
            logger.debug("Step 2/4: Extracting face region...")
            face_region = detection.get_face_region(image)

            # Step 4: Assess quality
            logger.debug("Step 3/4: Assessing quality...")
            quality = await self._quality_assessor.assess(face_region)

            if not quality.is_acceptable:
                issues = quality.get_issues()
                logger.warning(
                    f"Quality check failed: score={quality.score:.1f}, "
                    f"issues={issues}"
                )
                raise PoorImageQualityError(
                    quality_score=quality.score,
                    min_threshold=self._quality_assessor.get_minimum_acceptable_score(),
                    issues=issues,
                )

            logger.info(f"Quality check passed: score={quality.score:.1f}")

            # Step 5: Extract embedding
            logger.debug("Step 4/4: Extracting embedding...")
            embedding_vector = await self._extractor.extract(face_region)

            # Step 6: Save to repository
            await self._repository.save(
                user_id=user_id,
                embedding=embedding_vector,
                quality_score=quality.score,
                tenant_id=tenant_id,
            )

            # Step 7: Create and return result entity
            face_embedding = FaceEmbedding.create_new(
                user_id=user_id,
                vector=embedding_vector,
                quality_score=quality.score,
                tenant_id=tenant_id,
            )

            logger.info(
                f"Enrollment completed successfully for user_id={user_id}, "
                f"quality={quality.score:.1f}, "
                f"embedding_dim={len(embedding_vector)}"
            )

            return face_embedding

        finally:
            # CRITICAL: Explicitly release CV2 images to prevent memory leaks
            # Each image can be 10-50 MB depending on resolution
            # Without explicit cleanup, GC may not collect immediately
            if image is not None:
                del image
            if face_region is not None:
                del face_region
