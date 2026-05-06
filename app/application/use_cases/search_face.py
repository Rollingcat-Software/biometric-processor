"""Search face use case for 1:N identification."""

import logging
from dataclasses import dataclass
from typing import List, Optional

import cv2

from app.domain.exceptions.face_errors import FaceNotDetectedError, MultipleFacesError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

logger = logging.getLogger(__name__)


@dataclass
class SearchMatch:
    """Represents a search match result."""

    user_id: str
    distance: float
    confidence: float

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "user_id": self.user_id,
            "distance": round(self.distance, 4),
            "confidence": round(self.confidence, 4),
        }


@dataclass
class SearchResult:
    """Result of face search operation."""

    matches: List[SearchMatch]
    total_searched: int
    threshold: float

    @property
    def found(self) -> bool:
        """Check if any matches were found."""
        return len(self.matches) > 0

    @property
    def best_match(self) -> Optional[SearchMatch]:
        """Get the best match (lowest distance)."""
        return self.matches[0] if self.matches else None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "found": self.found,
            "matches": [m.to_dict() for m in self.matches],
            "total_searched": self.total_searched,
            "threshold": round(self.threshold, 4),
            "best_match": self.best_match.to_dict() if self.best_match else None,
        }


class SearchFaceUseCase:
    """Use case for searching a face across all enrolled users (1:N identification).

    This use case:
    1. Loads and validates the input image
    2. Detects face in the image
    3. Extracts face embedding
    4. Searches for similar embeddings in repository
    5. Returns ranked list of matches
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        repository: IEmbeddingRepository,
        similarity_calculator: ISimilarityCalculator,
    ) -> None:
        """Initialize search face use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            repository: Embedding repository implementation
            similarity_calculator: Similarity calculator for confidence scoring
        """
        self._detector = detector
        self._extractor = extractor
        self._repository = repository
        self._similarity_calculator = similarity_calculator

        logger.info("SearchFaceUseCase initialized")

    async def execute(
        self,
        image_path: str,
        max_results: int = 5,
        threshold: Optional[float] = None,
        tenant_id: Optional[str] = None,
    ) -> SearchResult:
        """Execute face search operation.

        Args:
            image_path: Path to face image
            max_results: Maximum number of matches to return
            threshold: Distance threshold for matching (None = use default)
            tenant_id: Optional tenant identifier for multi-tenant systems

        Returns:
            SearchResult with list of matches

        Raises:
            FaceNotDetectedError: When no face is detected
            MultipleFacesError: When multiple faces are detected
            ValueError: When image cannot be loaded
        """
        logger.info(
            f"Starting face search: max_results={max_results}, "
            f"threshold={threshold}, tenant_id={tenant_id}"
        )

        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Detect face
        detection = await self._detector.detect(image)
        if not detection.found:
            raise FaceNotDetectedError()

        # Check for multiple faces (optional - could support in future)
        # For now, we only process single face images
        if hasattr(detection, "face_count") and detection.face_count > 1:
            raise MultipleFacesError(count=detection.face_count)

        # USER-BUG-4 (2026-05-04): /search must use the cropped face region as
        # the embedding extractor input, NOT the full frame. Enrollment and
        # /verify both call ``detection.get_face_region(image)`` and pass the
        # crop to ``extractor.extract``; the DeepFace extractor runs with
        # ``enforce_detection=False`` because the upstream pipeline is
        # responsible for the crop. Passing the full frame here produced a
        # different embedding than the one stored at enrollment, so cosine
        # distance against the centroid never crossed the verification
        # threshold and /search always returned "no matches found" even when
        # /verify on the same image succeeded.
        face_region = detection.get_face_region(image)

        # Extract embedding (from the cropped face region — parity with
        # enroll_face.py and verify_face.py)
        embedding = await self._extractor.extract(face_region)

        # Get threshold from calculator if not provided
        if threshold is None:
            threshold = self._similarity_calculator.get_threshold()

        # Get total count for response
        total_count = await self._repository.count(tenant_id=tenant_id)

        # Search for similar embeddings
        similar = await self._repository.find_similar(
            embedding=embedding,
            threshold=threshold,
            limit=max_results,
            tenant_id=tenant_id,
        )

        # Convert to SearchMatch objects with confidence scores
        matches = []
        for user_id, distance in similar:
            # Calculate confidence as inverse of distance (higher is better, 0-1 range)
            confidence = max(0.0, min(1.0, 1 - distance))
            matches.append(
                SearchMatch(
                    user_id=user_id,
                    distance=distance,
                    confidence=confidence,
                )
            )

        logger.info(
            f"Face search complete: found {len(matches)} matches "
            f"out of {total_count} enrolled users"
        )

        return SearchResult(
            matches=matches,
            total_searched=total_count,
            threshold=threshold,
        )
