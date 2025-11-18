"""Quality assessor interface following Interface Segregation Principle."""

from typing import Protocol

import numpy as np

from app.domain.entities.quality_assessment import QualityAssessment


class IQualityAssessor(Protocol):
    """Protocol for image quality assessment implementations.

    Assesses various quality metrics to determine if an image is suitable
    for face recognition.
    """

    async def assess(self, face_image: np.ndarray) -> QualityAssessment:
        """Assess the quality of a face image.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            QualityAssessment containing quality metrics and overall score

        Raises:
            QualityAssessmentError: When quality assessment fails

        Note:
            Quality metrics include:
            - Blur detection (Laplacian variance)
            - Lighting assessment (mean brightness)
            - Face size (pixel dimensions)
            - Overall quality score (0-100)
        """
        ...

    def get_minimum_acceptable_score(self) -> float:
        """Get the minimum acceptable quality score.

        Returns:
            Minimum quality score (0-100) for acceptable images
        """
        ...
