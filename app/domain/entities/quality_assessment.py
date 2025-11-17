"""Quality assessment entity."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class QualityAssessment:
    """Result of image quality assessment.

    This is an immutable value object representing quality metrics.
    Following Single Responsibility Principle - only contains quality data.

    Attributes:
        score: Overall quality score (0-100), higher is better
        blur_score: Blur detection score (Laplacian variance)
        lighting_score: Lighting quality score (mean brightness)
        face_size: Face size in pixels (minimum dimension)
        is_acceptable: Whether quality meets minimum threshold

    Quality Guidelines:
        - score 0-40: Poor (reject)
        - score 41-70: Fair (warn user)
        - score 71-100: Good (accept)

    Note:
        This class is immutable (frozen) to ensure data integrity.
    """

    score: float
    blur_score: float
    lighting_score: float
    face_size: int
    is_acceptable: bool

    def __post_init__(self) -> None:
        """Validate quality assessment data."""
        if not 0 <= self.score <= 100:
            raise ValueError(f"Score must be 0-100, got {self.score}")

        if self.blur_score < 0:
            raise ValueError(f"Blur score cannot be negative: {self.blur_score}")

        if self.face_size < 0:
            raise ValueError(f"Face size cannot be negative: {self.face_size}")

    def get_quality_level(self) -> str:
        """Get quality level as string.

        Returns:
            Quality level: "poor", "fair", or "good"
        """
        if self.score < 40:
            return "poor"
        elif self.score < 71:
            return "fair"
        else:
            return "good"

    def is_blurry(self, blur_threshold: float = 100.0) -> bool:
        """Check if image is too blurry.

        Args:
            blur_threshold: Minimum acceptable blur score

        Returns:
            True if image is too blurry
        """
        return self.blur_score < blur_threshold

    def is_too_small(self, min_size: int = 80) -> bool:
        """Check if face is too small.

        Args:
            min_size: Minimum acceptable face size in pixels

        Returns:
            True if face is too small
        """
        return self.face_size < min_size

    def get_issues(self) -> Dict[str, Any]:
        """Get list of quality issues.

        Returns:
            Dictionary of quality issues with details
        """
        issues = {}

        if self.is_blurry():
            issues["blur"] = {
                "description": "Image is too blurry",
                "score": self.blur_score,
                "threshold": 100.0,
            }

        if self.is_too_small():
            issues["face_size"] = {
                "description": "Face is too small",
                "size": self.face_size,
                "minimum": 80,
            }

        if self.lighting_score < 50:
            issues["lighting"] = {
                "description": "Poor lighting conditions",
                "score": self.lighting_score,
            }

        return issues

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "score": self.score,
            "blur_score": self.blur_score,
            "lighting_score": self.lighting_score,
            "face_size": self.face_size,
            "is_acceptable": self.is_acceptable,
            "quality_level": self.get_quality_level(),
            "issues": self.get_issues(),
        }
