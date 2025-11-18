"""Enrollment API schemas."""

from pydantic import BaseModel, Field


class EnrollmentResponse(BaseModel):
    """Face enrollment response."""

    success: bool = Field(..., description="Whether enrollment was successful")
    user_id: str = Field(..., description="User identifier")
    quality_score: float = Field(..., ge=0, le=100, description="Image quality score (0-100)")
    message: str = Field(..., description="Human-readable message")
    embedding_dimension: int = Field(..., description="Dimension of face embedding")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "user_id": "user123",
                "quality_score": 85.5,
                "message": "Face enrolled successfully",
                "embedding_dimension": 128,
            }
        }
    }
