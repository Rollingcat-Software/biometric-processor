"""Face verification result entity."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class VerificationResult:
    """Result of face verification operation (1:1 matching).

    This is an immutable value object representing verification outcome.
    Following Single Responsibility Principle - only contains verification data.

    Attributes:
        verified: Whether the faces match
        confidence: Confidence score (0.0-1.0), higher = more confident
        distance: Similarity distance between embeddings, lower = more similar
        threshold: Threshold used for verification decision

    Note:
        This class is immutable (frozen) to ensure data integrity.
        verified = (distance < threshold)
    """

    verified: bool
    confidence: float
    distance: float
    threshold: float

    def __post_init__(self) -> None:
        """Validate verification result data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")

        if self.distance < 0.0:
            raise ValueError(f"Distance cannot be negative: {self.distance}")

        if self.threshold < 0.0:
            raise ValueError(f"Threshold cannot be negative: {self.threshold}")

        # Verify consistency
        expected_verified = self.distance < self.threshold
        if self.verified != expected_verified:
            raise ValueError(
                f"Inconsistent verification result: verified={self.verified} "
                f"but distance={self.distance} and threshold={self.threshold}"
            )

    def get_confidence_level(self) -> str:
        """Get confidence level as string.

        Returns:
            Confidence level: "low", "medium", or "high"
        """
        if self.confidence < 0.5:
            return "low"
        elif self.confidence < 0.8:
            return "medium"
        else:
            return "high"

    def is_strong_match(self, threshold: float = 0.9) -> bool:
        """Check if this is a strong match.

        Args:
            threshold: Minimum confidence for strong match

        Returns:
            True if confidence exceeds threshold and verified
        """
        return self.verified and self.confidence >= threshold

    def is_weak_match(self) -> bool:
        """Check if this is a weak match (close to threshold).

        Returns:
            True if verified but confidence is close to threshold
        """
        if not self.verified:
            return False

        # Close to threshold means within 10% margin
        margin = self.threshold * 0.1
        return abs(self.distance - self.threshold) < margin

    def get_similarity_percentage(self) -> float:
        """Get similarity as percentage (0-100).

        Returns:
            Similarity percentage
        """
        return self.confidence * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "verified": self.verified,
            "confidence": self.confidence,
            "distance": self.distance,
            "threshold": self.threshold,
            "confidence_level": self.get_confidence_level(),
            "similarity_percentage": self.get_similarity_percentage(),
            "strong_match": self.is_strong_match(),
            "weak_match": self.is_weak_match(),
        }
