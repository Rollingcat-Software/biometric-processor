"""Quality assessment entity."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


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
        yaw: Estimated head yaw angle in degrees (None if landmarks unavailable)
        pitch: Estimated head pitch angle in degrees (None if landmarks unavailable)
        pose_acceptable: Whether head pose is within acceptable range (None if unavailable)

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
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    pose_acceptable: Optional[bool] = None

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

    def get_issues(self, blur_threshold: float = 15.0, min_face_size: int = 60) -> Dict[str, Any]:
        """Get list of quality issues with actual thresholds.

        Args:
            blur_threshold: Actual blur threshold used by the assessor
            min_face_size: Actual minimum face size used by the assessor

        Returns:
            Dictionary of quality issues with details
        """
        issues = {}

        if self.blur_score < blur_threshold:
            issues["blur"] = {
                "description": "Image is too blurry",
                "score": self.blur_score,
                "threshold": blur_threshold,
            }

        if self.face_size < min_face_size:
            issues["face_size"] = {
                "description": "Face is too small",
                "size": self.face_size,
                "minimum": min_face_size,
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
            "yaw": self.yaw,
            "pitch": self.pitch,
            "pose_acceptable": self.pose_acceptable,
        }
