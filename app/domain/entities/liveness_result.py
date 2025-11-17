"""Liveness detection result entity."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class LivenessResult:
    """Result of liveness detection operation.

    This is an immutable value object representing liveness check outcome.
    Following Single Responsibility Principle - only contains liveness data.

    Attributes:
        is_live: Whether the subject is determined to be a live person
        liveness_score: Liveness score (0-100), higher = more likely live
        challenge: Type of challenge used (e.g., "smile", "blink")
        challenge_completed: Whether the challenge was successfully completed

    Liveness Score Guidelines:
        - 0-50: Likely spoof (reject)
        - 51-80: Uncertain (additional verification recommended)
        - 81-100: Live person (accept)

    Note:
        This class is immutable (frozen) to ensure data integrity.
    """

    is_live: bool
    liveness_score: float
    challenge: str
    challenge_completed: bool

    def __post_init__(self) -> None:
        """Validate liveness result data."""
        if not 0 <= self.liveness_score <= 100:
            raise ValueError(f"Liveness score must be 0-100, got {self.liveness_score}")

        if not self.challenge:
            raise ValueError("Challenge type cannot be empty")

    def get_confidence_level(self) -> str:
        """Get confidence level as string.

        Returns:
            Confidence level: "low", "medium", or "high"
        """
        if self.liveness_score < 50:
            return "low"
        elif self.liveness_score < 81:
            return "medium"
        else:
            return "high"

    def is_spoof_suspected(self, threshold: float = 50.0) -> bool:
        """Check if spoof attack is suspected.

        Args:
            threshold: Minimum acceptable liveness score

        Returns:
            True if liveness score below threshold
        """
        return self.liveness_score < threshold

    def requires_additional_verification(self, threshold: float = 80.0) -> bool:
        """Check if additional verification is recommended.

        Args:
            threshold: Threshold for requiring additional verification

        Returns:
            True if liveness score is uncertain (between 50-80)
        """
        return 50 <= self.liveness_score < threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "is_live": self.is_live,
            "liveness_score": self.liveness_score,
            "challenge": self.challenge,
            "challenge_completed": self.challenge_completed,
            "confidence_level": self.get_confidence_level(),
            "spoof_suspected": self.is_spoof_suspected(),
            "requires_additional_verification": self.requires_additional_verification(),
        }
