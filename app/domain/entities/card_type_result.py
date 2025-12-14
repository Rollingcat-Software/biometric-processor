"""Card type detection result entities."""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel


@dataclass
class CardTypeResult:
    """Domain entity for card type detection result.

    Attributes:
        detected: Whether a card was detected
        class_id: ID of detected card class
        class_name: Name of detected card class
        confidence: Detection confidence score (0.0 to 1.0)
    """

    detected: bool
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: Optional[float] = None


class CardTypeResponse(BaseModel):
    """API response model for card type detection."""

    detected: bool
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: Optional[float] = None

    @classmethod
    def from_result(cls, result: CardTypeResult) -> "CardTypeResponse":
        """Create response from domain result."""
        return cls(
            detected=result.detected,
            class_id=result.class_id,
            class_name=result.class_name,
            confidence=result.confidence,
        )

