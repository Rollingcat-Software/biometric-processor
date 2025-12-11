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

        # Process first image
        face1_info = self._process_face(image1, "first")

        # Process second image
        face2_info = self._process_face(image2, "second")

        # Extract embeddings
        embedding1 = self._extractor.extract(image1)
        embedding2 = self._extractor.extract(image2)

        # Calculate similarity
        similarity_result = self._similarity_calculator.calculate(
            embedding1.embedding, embedding2.embedding
        )

        # Determine match and confidence
        similarity = similarity_result.similarity
        match = similarity >= threshold
        confidence = self._get_confidence_level(similarity, threshold)

        # Create result
        distance = 1.0 - similarity
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

    def _process_face(self, image: np.ndarray, name: str) -> FaceInfo:
        """Process face and extract info."""
        detection = self._detector.detect(image)

        if not detection.face_detected:
            raise FaceNotFoundError(f"No face detected in {name} image")

        # Get quality score
        try:
            quality_result = self._quality_assessor.assess(image)
            quality_score = (
                quality_result.overall_score
                if hasattr(quality_result, "overall_score")
                else 0.0
            )
        except Exception:
            quality_score = 0.0

        # Get bounding box
        bbox = None
        if detection.face_coordinates:
            x, y, w, h = detection.face_coordinates
            bbox = BoundingBox(x=x, y=y, width=w, height=h)

        return FaceInfo(
            detected=True,
            quality_score=quality_score,
            bounding_box=bbox,
        )

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
