"""Liveness check API schemas."""

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    """Liveness check response."""

    is_live: bool = Field(..., description="Whether subject is determined to be live")
    score: float = Field(..., ge=0.0, le=100.0, description="Decision score (0-100)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence (0-1)")
    challenge: str = Field(..., description="Challenge type used")
    challenge_completed: bool = Field(..., description="Whether challenge was completed")
    message: str = Field(..., description="Human-readable message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "is_live": True,
                "score": 92.5,
                "confidence": 0.91,
                "challenge": "smile",
                "challenge_completed": True,
                "message": "Liveness check passed",
            }
        }
    }
