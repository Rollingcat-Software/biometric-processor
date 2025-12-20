"""Compare faces use case."""

import logging

import numpy as np

from app.domain.entities.face_comparison import (
    BoundingBox,
    FaceComparisonResult,
    FaceInfo,
)
from app.domain.exceptions.face_errors import FaceNotFoundError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

logger = logging.getLogger(__name__)


class CompareFacesUseCase:
    """Use case for comparing two face images directly.

    Compares two images without requiring enrollment.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
        quality_assessor: IQualityAssessor,
    ) -> None:
        """Initialize face comparison use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            similarity_calculator: Similarity calculator implementation
            quality_assessor: Quality assessor implementation
        """
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        self._quality_assessor = quality_assessor
        logger.info("CompareFacesUseCase initialized")

    async def execute(
        self,
        image1: np.ndarray,
        image2: np.ndarray,
        threshold: float = 0.6,
    ) -> FaceComparisonResult:
        """Execute face comparison.

        Args:
            image1: First face image
            image2: Second face image
            threshold: Similarity threshold for match

        Returns:
            FaceComparisonResult with comparison details

        Raises:
            FaceNotFoundError: When face not detected in either image
        """
        logger.info("Starting face comparison")

        # Process first image - detect face and get info
        face1_info, face1_region = await self._process_face(image1, "first")

        # Process second image - detect face and get info
        face2_info, face2_region = await self._process_face(image2, "second")

        # Extract embeddings from face regions
        embedding1 = await self._extractor.extract(face1_region)
        embedding2 = await self._extractor.extract(face2_region)

        # Calculate distance (lower = more similar)
        distance = self._similarity_calculator.calculate(embedding1, embedding2)

        # Convert distance to similarity (higher = more similar)
        similarity = max(0.0, 1.0 - distance)
        match = distance < threshold
        confidence = self._get_confidence_level(similarity, threshold)

        # Create result
        message = self._get_result_message(match, confidence)

        result = FaceComparisonResult(
            match=match,
            similarity=round(similarity, 4),
            distance=round(distance, 4),
            threshold=threshold,
            confidence=confidence,
            face1=face1_info,
            face2=face2_info,
            message=message,
        )

        logger.info(
            f"Face comparison complete: match={match}, similarity={similarity:.4f}"
        )

        return result

    async def _process_face(
        self, image: np.ndarray, name: str
    ) -> tuple[FaceInfo, np.ndarray]:
        """Process face and extract info.

        Args:
            image: Input image
            name: Name for error messages (e.g., "first", "second")

        Returns:
            Tuple of (FaceInfo, face_region)

        Raises:
            FaceNotFoundError: When no face is detected
        """
        detection = await self._detector.detect(image)

        if not detection.found:
            raise FaceNotFoundError(f"No face detected in {name} image")

        # Extract face region
        face_region = detection.get_face_region(image)

        # Get quality score
        quality_score = 0.0
        try:
            quality_result = await self._quality_assessor.assess(face_region)
            quality_score = quality_result.score
        except Exception as e:
            logger.warning(f"Quality assessment failed for {name} image: {e}")

        # Get bounding box
        bbox = None
        if detection.bounding_box:
            x, y, w, h = detection.bounding_box
            bbox = BoundingBox(x=x, y=y, width=w, height=h)

        face_info = FaceInfo(
            detected=True,
            quality_score=quality_score,
            bounding_box=bbox,
        )

        return face_info, face_region

    def _get_confidence_level(self, similarity: float, threshold: float) -> str:
        """Determine confidence level from similarity."""
        if similarity >= threshold + 0.2:
            return "high"
        elif similarity >= threshold + 0.1:
            return "medium"
        elif similarity >= threshold:
            return "low"
        else:
            return "low"

    def _get_result_message(self, match: bool, confidence: str) -> str:
        """Generate human-readable result message."""
        if match:
            return f"Faces match with {confidence} confidence"
        else:
            return "Faces do not match"
