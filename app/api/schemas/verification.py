"""Verification API schemas."""

from pydantic import BaseModel, Field


class VerificationRequest(BaseModel):
    """Face verification request (not used with multipart/form-data, kept for reference)."""

    user_id: str = Field(..., description="User identifier to verify against")


class VerificationResponse(BaseModel):
    """Face verification response."""

    verified: bool = Field(..., description="Whether faces match")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    distance: float = Field(..., ge=0.0, description="Similarity distance")
    threshold: float = Field(..., description="Threshold used for verification")
    message: str = Field(..., description="Human-readable message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "verified": True,
                "confidence": 0.87,
                "distance": 0.13,
                "threshold": 0.6,
                "message": "Face verified successfully",
            }
        }
    }
