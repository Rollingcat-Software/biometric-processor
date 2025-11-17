"""Face verification use case."""

import logging
import cv2
from typing import Optional

from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.entities.verification_result import VerificationResult
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError

logger = logging.getLogger(__name__)


class VerifyFaceUseCase:
    """Use case for verifying a user's face (1:1 matching).

    This use case orchestrates the following steps:
    1. Detect face in image
    2. Extract face region
    3. Extract embedding
    4. Retrieve stored embedding from repository
    5. Calculate similarity
    6. Verify against threshold

    Following Single Responsibility Principle: Only handles verification orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
        repository: IEmbeddingRepository,
    ) -> None:
        """Initialize verification use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            similarity_calculator: Similarity calculator implementation
            repository: Embedding repository implementation
        """
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        self._repository = repository

        logger.info("VerifyFaceUseCase initialized")

    async def execute(
        self,
        user_id: str,
        image_path: str,
        tenant_id: Optional[str] = None,
    ) -> VerificationResult:
        """Execute face verification.

        Args:
            user_id: User identifier to verify against
            image_path: Path to image file
            tenant_id: Optional tenant identifier for multi-tenancy

        Returns:
            VerificationResult with verification outcome

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            EmbeddingNotFoundError: When no stored embedding exists for user
            EmbeddingExtractionError: When embedding extraction fails
            RepositoryError: When repository access fails
        """
        logger.info(f"Starting face verification for user_id={user_id}, tenant_id={tenant_id}")

        # Step 1: Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Step 2: Detect face
        logger.debug("Step 1/5: Detecting face...")
        detection = await self._detector.detect(image)

        # Step 3: Extract face region
        logger.debug("Step 2/5: Extracting face region...")
        face_region = detection.get_face_region(image)

        # Step 4: Extract embedding from new image
        logger.debug("Step 3/5: Extracting embedding...")
        new_embedding = await self._extractor.extract(face_region)

        # Step 5: Retrieve stored embedding
        logger.debug("Step 4/5: Retrieving stored embedding...")
        stored_embedding = await self._repository.find_by_user_id(user_id, tenant_id)

        if stored_embedding is None:
            logger.warning(f"No embedding found for user_id={user_id}")
            raise EmbeddingNotFoundError(user_id)

        # Step 6: Calculate similarity
        logger.debug("Step 5/5: Calculating similarity...")
        distance = self._similarity_calculator.calculate(new_embedding, stored_embedding)

        # Step 7: Verify against threshold
        threshold = self._similarity_calculator.get_threshold()
        verified = distance < threshold
        confidence = self._similarity_calculator.get_confidence(distance)

        logger.info(
            f"Verification completed: user_id={user_id}, "
            f"verified={verified}, "
            f"distance={distance:.4f}, "
            f"confidence={confidence:.4f}, "
            f"threshold={threshold}"
        )

        return VerificationResult(
            verified=verified,
            confidence=confidence,
            distance=distance,
            threshold=threshold,
        )
