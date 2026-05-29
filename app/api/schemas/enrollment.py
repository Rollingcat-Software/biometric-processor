"""Enrollment API schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class EnrollmentResponse(BaseModel):
    """Face enrollment response."""

    success: bool = Field(..., description="Whether enrollment was successful")
    user_id: str = Field(..., description="User identifier")
    quality_score: float = Field(..., ge=0, le=100, description="Image quality score (0-100)")
    message: str = Field(..., description="Human-readable message")
    embedding_dimension: int = Field(..., description="Dimension of face embedding")
    # 0-100 decision score from the passive liveness check (same scale as
    # LivenessResult.score and LIVENESS_THRESHOLD). None when the enroll-time
    # liveness gate is disabled (ENROLL_LIVENESS_ENABLED=false).
    liveness_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Passive liveness decision score (0-100). None when the enroll "
            "liveness gate is disabled (ENROLL_LIVENESS_ENABLED=false)."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "user_id": "user123",
                "quality_score": 85.5,
                "message": "Face enrolled successfully",
                "embedding_dimension": 128,
                "liveness_score": 92.0,
            }
        }
    }
