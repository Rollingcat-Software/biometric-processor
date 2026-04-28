"""Face verification use case."""

import logging
from datetime import datetime
from typing import Optional

import cv2

from app.core.config import settings
from app.domain.entities.verification_result import VerificationResult
from app.domain.exceptions.face_errors import PoorImageQualityError
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

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

    # Verification quality threshold (more lenient than enrollment's 70)
    VERIFICATION_QUALITY_THRESHOLD = 50.0

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
        repository: IEmbeddingRepository,
        quality_assessor: IQualityAssessor | None = None,
    ) -> None:
        """Initialize verification use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            similarity_calculator: Similarity calculator implementation
            repository: Embedding repository implementation
            quality_assessor: Optional quality assessor for pre-verification gating
        """
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        self._repository = repository
        self._quality_assessor = quality_assessor

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
        # Client pre-crops to 224×224 — detection only as fallback.
        # When the input image is already ~224×224 (client-cropped), this step
        # is fast (<10ms) because there is only one face region covering most of
        # the frame. Full-frame detection (640×480+) previously cost 200-730ms.
        logger.debug("Step 1/5: Detecting face...")
        detection = await self._detector.detect(image)

        # Step 3: Extract face region
        logger.debug("Step 2/6: Extracting face region...")
        face_region = detection.get_face_region(image)

        # Step 4: Quality gate (reject poor images before expensive comparison)
        if self._quality_assessor is not None:
            logger.debug("Step 3/6: Assessing image quality...")
            quality = await self._quality_assessor.assess(face_region)

            if quality.score < self.VERIFICATION_QUALITY_THRESHOLD:
                issues = quality.get_issues(
                    blur_threshold=self._quality_assessor._blur_threshold,
                    min_face_size=self._quality_assessor._min_face_size,
                )
                logger.warning(
                    f"Verification quality gate failed: score={quality.score:.1f}, "
                    f"threshold={self.VERIFICATION_QUALITY_THRESHOLD}, issues={issues}"
                )
                raise PoorImageQualityError(
                    quality_score=quality.score,
                    min_threshold=self.VERIFICATION_QUALITY_THRESHOLD,
                    issues=issues,
                )
            logger.info(f"Verification quality check passed: score={quality.score:.1f}")

        # Step 5: Extract embedding from new image
        logger.debug("Step 4/6: Extracting embedding...")
        new_embedding = await self._extractor.extract(face_region)

        # Step 6: Retrieve stored embedding
        logger.debug("Step 5/6: Retrieving stored embedding...")
        stored_embedding = await self._repository.find_by_user_id(user_id, tenant_id)

        if stored_embedding is None:
            logger.warning(f"No embedding found for user_id={user_id}")
            raise EmbeddingNotFoundError(user_id)

        # Step 7: Calculate similarity
        logger.debug("Step 6/6: Calculating similarity...")
        distance = self._similarity_calculator.calculate(new_embedding, stored_embedding)

        # Step 7: Determine threshold — use adaptive (lenient) threshold for aged embeddings
        threshold = self._similarity_calculator.get_threshold()
        try:
            if hasattr(self._repository, "find_created_at"):
                created_at = await self._repository.find_created_at(user_id, tenant_id)
                if created_at is not None:
                    days = (datetime.utcnow() - created_at).days
                    aged_threshold_days = int(settings.VERIFICATION_THRESHOLD_AGED_YEARS * 365)
                    if days > aged_threshold_days:
                        threshold = settings.VERIFICATION_THRESHOLD_AGED
                        logger.info(
                            f"Adaptive threshold applied: embedding_age={days}d "
                            f"(>{aged_threshold_days}d), threshold={threshold} "
                            f"(was {self._similarity_calculator.get_threshold()})"
                        )
        except Exception as _threshold_err:
            logger.warning(f"Adaptive threshold lookup failed, using default: {_threshold_err}")

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
