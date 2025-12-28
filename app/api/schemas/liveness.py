"""Liveness check API schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class LivenessCheck(BaseModel):
    """Individual liveness check result."""

    name: str = Field(..., description="Check name (e.g., 'texture', 'color', 'moire')")
    passed: bool = Field(..., description="Whether this check passed")
    score: float = Field(..., ge=0.0, le=100.0, description="Check score (0-100)")
    details: str = Field(..., description="Human-readable details about the check")


class LivenessResponse(BaseModel):
    """Liveness check response."""

    is_live: bool = Field(..., description="Whether subject is determined to be live")
    liveness_score: float = Field(..., ge=0.0, le=100.0, description="Liveness score (0-100)")
    challenge: str = Field(..., description="Challenge type used")
    challenge_completed: bool = Field(..., description="Whether challenge was completed")
    message: str = Field(..., description="Human-readable message")
    checks: List[LivenessCheck] = Field(
        default_factory=list,
        description="Individual check results"
    )
    spoof_type: Optional[str] = Field(
        default=None,
        description="Detected spoof type if not live (screen_replay, printed_photo, etc.)"
    )
    processing_time_ms: Optional[float] = Field(
        default=None,
        description="Processing time in milliseconds"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "is_live": True,
                "liveness_score": 92.5,
                "challenge": "combined",
                "challenge_completed": True,
                "message": "Liveness check passed - live person detected",
                "checks": [
                    {"name": "texture", "passed": True, "score": 85.0, "details": "Good texture variance"},
                    {"name": "color", "passed": True, "score": 90.0, "details": "Natural color distribution"},
                    {"name": "moire", "passed": True, "score": 95.0, "details": "No screen patterns detected"},
                    {"name": "face_landmarks", "passed": True, "score": 88.0, "details": "Face landmarks detected"},
                ],
                "spoof_type": None,
                "processing_time_ms": 245.3,
            }
        }
    }
