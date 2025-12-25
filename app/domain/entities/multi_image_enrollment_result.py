"""Multi-image enrollment result entity."""

from dataclasses import dataclass
from typing import List

from app.domain.entities.face_embedding import FaceEmbedding


@dataclass
class MultiImageEnrollmentResult:
    """Result of multi-image enrollment operation.

    This entity encapsulates all information about a successful multi-image
    enrollment, including individual image quality scores and the fused result.

    Attributes:
        face_embedding: The fused face embedding result
        individual_quality_scores: Quality scores for each processed image
        images_processed: Number of images successfully processed
        average_quality_score: Average quality across all images
        fusion_strategy: Strategy used for fusion (e.g., "weighted_average")
    """

    face_embedding: FaceEmbedding
    individual_quality_scores: List[float]
    images_processed: int
    average_quality_score: float
    fusion_strategy: str

    def __post_init__(self) -> None:
        """Validate result data."""
        if self.images_processed < 2:
            raise ValueError("Multi-image enrollment requires at least 2 images")

        if len(self.individual_quality_scores) != self.images_processed:
            raise ValueError(
                f"Quality scores count ({len(self.individual_quality_scores)}) "
                f"must match images processed ({self.images_processed})"
            )

        if not all(0 <= score <= 100 for score in self.individual_quality_scores):
            raise ValueError("All quality scores must be between 0 and 100")

        if not 0 <= self.average_quality_score <= 100:
            raise ValueError(
                f"Average quality score must be 0-100, got {self.average_quality_score}"
            )

    @property
    def user_id(self) -> str:
        """Get user_id from the face embedding."""
        return self.face_embedding.user_id

    @property
    def tenant_id(self) -> str:
        """Get tenant_id from the face embedding."""
        return self.face_embedding.tenant_id

    @property
    def fused_quality_score(self) -> float:
        """Get the fused quality score from the face embedding."""
        return self.face_embedding.quality_score

    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.face_embedding.get_embedding_dimension()

    def get_quality_improvement(self) -> float:
        """Calculate quality improvement from fusion.

        Returns:
            Percentage improvement from average to fused quality
        """
        if self.average_quality_score == 0:
            return 0.0

        improvement = (
            (self.fused_quality_score - self.average_quality_score)
            / self.average_quality_score
        ) * 100
        return improvement

    @classmethod
    def create(
        cls,
        face_embedding: FaceEmbedding,
        individual_quality_scores: List[float],
        fusion_strategy: str = "weighted_average",
    ) -> "MultiImageEnrollmentResult":
        """Factory method to create multi-image enrollment result.

        Args:
            face_embedding: The fused face embedding
            individual_quality_scores: Quality scores for each image
            fusion_strategy: Strategy used for fusion

        Returns:
            New MultiImageEnrollmentResult instance
        """
        images_processed = len(individual_quality_scores)
        average_quality = sum(individual_quality_scores) / images_processed

        return cls(
            face_embedding=face_embedding,
            individual_quality_scores=individual_quality_scores,
            images_processed=images_processed,
            average_quality_score=average_quality,
            fusion_strategy=fusion_strategy,
        )
