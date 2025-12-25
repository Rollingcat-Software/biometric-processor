"""Multi-image enrollment API schemas."""

from typing import List

from pydantic import BaseModel, Field


class MultiImageEnrollmentResponse(BaseModel):
    """Multi-image face enrollment response."""

    success: bool = Field(..., description="Whether enrollment was successful")
    user_id: str = Field(..., description="User identifier")
    images_processed: int = Field(..., ge=2, le=5, description="Number of images processed")
    fused_quality_score: float = Field(
        ..., ge=0, le=100, description="Quality score of fused template (0-100)"
    )
    average_quality_score: float = Field(
        ..., ge=0, le=100, description="Average quality of individual images (0-100)"
    )
    individual_quality_scores: List[float] = Field(
        ..., description="Quality scores of individual images"
    )
    message: str = Field(..., description="Human-readable message")
    embedding_dimension: int = Field(..., description="Dimension of fused embedding")
    fusion_strategy: str = Field(default="weighted_average", description="Fusion strategy used")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "user_id": "user123",
                "images_processed": 3,
                "fused_quality_score": 87.5,
                "average_quality_score": 82.3,
                "individual_quality_scores": [78.5, 85.0, 83.5],
                "message": "Multi-image enrollment completed successfully",
                "embedding_dimension": 512,
                "fusion_strategy": "weighted_average",
            }
        }
    }


class MultiImageEnrollmentRequest(BaseModel):
    """Multi-image enrollment request (for documentation)."""

    user_id: str = Field(..., description="User identifier")
    tenant_id: str = Field(None, description="Optional tenant identifier")
    files: List[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="2-5 face images (uploaded as multipart/form-data)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user123",
                "tenant_id": "tenant_abc",
                "files": ["image1.jpg", "image2.jpg", "image3.jpg"],
            }
        }
    }
