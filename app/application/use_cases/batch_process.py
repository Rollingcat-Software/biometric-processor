"""Batch processing use cases for biometric operations."""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import cv2

from app.domain.exceptions.face_errors import (
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
)
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

logger = logging.getLogger(__name__)


class BatchOperationStatus(str, Enum):
    """Status of individual batch operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchItemResult:
    """Result of a single item in batch operation."""

    item_id: str
    status: BatchOperationStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class BatchEnrollmentResult:
    """Result of batch enrollment operation."""

    total_items: int
    successful: int
    failed: int
    skipped: int
    results: List[BatchItemResult] = field(default_factory=list)


@dataclass
class BatchVerificationResult:
    """Result of batch verification operation."""

    total_items: int
    successful: int
    failed: int
    results: List[BatchItemResult] = field(default_factory=list)


@dataclass
class EnrollmentItem:
    """Single item for batch enrollment."""

    user_id: str
    image_path: str
    tenant_id: Optional[str] = None


@dataclass
class VerificationItem:
    """Single item for batch verification."""

    item_id: str
    user_id: str
    image_path: str
    tenant_id: Optional[str] = None


class BatchEnrollmentUseCase:
    """Use case for batch face enrollment.

    Processes multiple enrollment requests concurrently with configurable
    parallelism and error handling.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        quality_assessor: IQualityAssessor,
        repository: IEmbeddingRepository,
        max_concurrent: int = 5,
    ) -> None:
        """Initialize batch enrollment use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            quality_assessor: Quality assessor implementation
            repository: Embedding repository implementation
            max_concurrent: Maximum concurrent operations
        """
        self._detector = detector
        self._extractor = extractor
        self._quality_assessor = quality_assessor
        self._repository = repository
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(f"BatchEnrollmentUseCase initialized (max_concurrent={max_concurrent})")

    async def execute(
        self,
        items: List[EnrollmentItem],
        skip_duplicates: bool = True,
    ) -> BatchEnrollmentResult:
        """Execute batch enrollment.

        Args:
            items: List of enrollment items to process
            skip_duplicates: Whether to skip users that already exist

        Returns:
            BatchEnrollmentResult with status of each item
        """
        logger.info(f"Starting batch enrollment for {len(items)} items")

        results: List[BatchItemResult] = []
        successful = 0
        failed = 0
        skipped = 0

        # Process items concurrently with semaphore
        tasks = [self._process_enrollment_item(item, skip_duplicates) for item in items]
        item_results = await asyncio.gather(*tasks)

        for result in item_results:
            results.append(result)
            if result.status == BatchOperationStatus.SUCCESS:
                successful += 1
            elif result.status == BatchOperationStatus.FAILED:
                failed += 1
            else:
                skipped += 1

        logger.info(
            f"Batch enrollment completed: "
            f"{successful} successful, {failed} failed, {skipped} skipped"
        )

        return BatchEnrollmentResult(
            total_items=len(items),
            successful=successful,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    async def _process_enrollment_item(
        self,
        item: EnrollmentItem,
        skip_duplicates: bool,
    ) -> BatchItemResult:
        """Process a single enrollment item.

        Args:
            item: Enrollment item to process
            skip_duplicates: Whether to skip if user exists

        Returns:
            BatchItemResult for this item
        """
        async with self._semaphore:
            try:
                # Check if user already exists
                if skip_duplicates:
                    existing = await self._repository.find_by_user_id(
                        item.user_id,
                        item.tenant_id,
                    )
                    if existing:
                        logger.debug(f"Skipping duplicate user: {item.user_id}")
                        return BatchItemResult(
                            item_id=item.user_id,
                            status=BatchOperationStatus.SKIPPED,
                            error="User already enrolled",
                            error_code="DUPLICATE_USER",
                        )

                # Load image
                image = cv2.imread(item.image_path)
                if image is None:
                    return BatchItemResult(
                        item_id=item.user_id,
                        status=BatchOperationStatus.FAILED,
                        error=f"Failed to load image: {item.image_path}",
                        error_code="IMAGE_LOAD_ERROR",
                    )

                # Detect face
                detection = await self._detector.detect(image)

                # Extract face region
                face_region = detection.get_face_region(image)

                # Assess quality
                quality = await self._quality_assessor.assess(face_region)

                if not quality.is_acceptable:
                    return BatchItemResult(
                        item_id=item.user_id,
                        status=BatchOperationStatus.FAILED,
                        error=f"Quality check failed: score={quality.score:.1f}",
                        error_code="POOR_QUALITY",
                        data={"quality_score": quality.score},
                    )

                # Extract embedding
                embedding_vector = await self._extractor.extract(face_region)

                # Save to repository
                await self._repository.save(
                    user_id=item.user_id,
                    embedding=embedding_vector,
                    quality_score=quality.score,
                    tenant_id=item.tenant_id,
                )

                logger.debug(f"Successfully enrolled user: {item.user_id}")

                return BatchItemResult(
                    item_id=item.user_id,
                    status=BatchOperationStatus.SUCCESS,
                    data={
                        "quality_score": quality.score,
                        "embedding_dim": len(embedding_vector),
                    },
                )

            except FaceNotDetectedError:
                return BatchItemResult(
                    item_id=item.user_id,
                    status=BatchOperationStatus.FAILED,
                    error="No face detected in image",
                    error_code="NO_FACE_DETECTED",
                )
            except MultipleFacesError as e:
                return BatchItemResult(
                    item_id=item.user_id,
                    status=BatchOperationStatus.FAILED,
                    error=str(e),
                    error_code="MULTIPLE_FACES",
                )
            except PoorImageQualityError as e:
                return BatchItemResult(
                    item_id=item.user_id,
                    status=BatchOperationStatus.FAILED,
                    error=str(e),
                    error_code="POOR_QUALITY",
                )
            except Exception as e:
                logger.error(f"Error enrolling {item.user_id}: {e}", exc_info=True)
                return BatchItemResult(
                    item_id=item.user_id,
                    status=BatchOperationStatus.FAILED,
                    error=str(e),
                    error_code="UNKNOWN_ERROR",
                )


class BatchVerificationUseCase:
    """Use case for batch face verification.

    Processes multiple verification requests concurrently.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        repository: IEmbeddingRepository,
        similarity_calculator: ISimilarityCalculator,
        max_concurrent: int = 5,
        default_threshold: float = 0.6,
    ) -> None:
        """Initialize batch verification use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            repository: Embedding repository implementation
            similarity_calculator: Similarity calculator implementation
            max_concurrent: Maximum concurrent operations
            default_threshold: Default similarity threshold
        """
        self._detector = detector
        self._extractor = extractor
        self._repository = repository
        self._similarity_calculator = similarity_calculator
        self._max_concurrent = max_concurrent
        self._default_threshold = default_threshold
        self._semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(f"BatchVerificationUseCase initialized (max_concurrent={max_concurrent})")

    async def execute(
        self,
        items: List[VerificationItem],
        threshold: Optional[float] = None,
    ) -> BatchVerificationResult:
        """Execute batch verification.

        Args:
            items: List of verification items to process
            threshold: Optional custom similarity threshold

        Returns:
            BatchVerificationResult with status of each item
        """
        logger.info(f"Starting batch verification for {len(items)} items")

        threshold = threshold or self._default_threshold
        results: List[BatchItemResult] = []
        successful = 0
        failed = 0

        # Process items concurrently with semaphore
        tasks = [self._process_verification_item(item, threshold) for item in items]
        item_results = await asyncio.gather(*tasks)

        for result in item_results:
            results.append(result)
            if result.status == BatchOperationStatus.SUCCESS:
                successful += 1
            else:
                failed += 1

        logger.info(f"Batch verification completed: " f"{successful} successful, {failed} failed")

        return BatchVerificationResult(
            total_items=len(items),
            successful=successful,
            failed=failed,
            results=results,
        )

    async def _process_verification_item(
        self,
        item: VerificationItem,
        threshold: float,
    ) -> BatchItemResult:
        """Process a single verification item.

        Args:
            item: Verification item to process
            threshold: Similarity threshold

        Returns:
            BatchItemResult for this item
        """
        async with self._semaphore:
            try:
                # Load image
                image = cv2.imread(item.image_path)
                if image is None:
                    return BatchItemResult(
                        item_id=item.item_id,
                        status=BatchOperationStatus.FAILED,
                        error=f"Failed to load image: {item.image_path}",
                        error_code="IMAGE_LOAD_ERROR",
                    )

                # Get stored embedding
                stored = await self._repository.find_by_user_id(
                    item.user_id,
                    item.tenant_id,
                )
                if not stored:
                    return BatchItemResult(
                        item_id=item.item_id,
                        status=BatchOperationStatus.FAILED,
                        error=f"User not enrolled: {item.user_id}",
                        error_code="USER_NOT_FOUND",
                    )

                # Detect face
                detection = await self._detector.detect(image)

                # Extract face region
                face_region = detection.get_face_region(image)

                # Extract embedding
                probe_embedding = await self._extractor.extract(face_region)

                # Calculate similarity
                distance = self._similarity_calculator.calculate(
                    probe_embedding,
                    stored.embedding,
                )
                is_match = distance < threshold
                confidence = max(0.0, min(100.0, (1 - distance) * 100))

                logger.debug(
                    f"Verification {item.item_id}: "
                    f"match={is_match}, distance={distance:.4f}, confidence={confidence:.1f}"
                )

                return BatchItemResult(
                    item_id=item.item_id,
                    status=BatchOperationStatus.SUCCESS,
                    data={
                        "user_id": item.user_id,
                        "is_match": is_match,
                        "distance": round(distance, 4),
                        "confidence": round(confidence, 2),
                        "threshold": threshold,
                    },
                )

            except FaceNotDetectedError:
                return BatchItemResult(
                    item_id=item.item_id,
                    status=BatchOperationStatus.FAILED,
                    error="No face detected in image",
                    error_code="NO_FACE_DETECTED",
                )
            except MultipleFacesError as e:
                return BatchItemResult(
                    item_id=item.item_id,
                    status=BatchOperationStatus.FAILED,
                    error=str(e),
                    error_code="MULTIPLE_FACES",
                )
            except Exception as e:
                logger.error(f"Error verifying {item.item_id}: {e}", exc_info=True)
                return BatchItemResult(
                    item_id=item.item_id,
                    status=BatchOperationStatus.FAILED,
                    error=str(e),
                    error_code="UNKNOWN_ERROR",
                )
