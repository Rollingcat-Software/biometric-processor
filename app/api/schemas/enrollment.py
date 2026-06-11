"""Enrollment API schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.verification import EMBEDDING_DIMENSION


class EmbeddingEnrollRequest(BaseModel):
    """Request body for ``POST /enroll-embedding`` (client-side embedding).

    The client computed the Facenet512 embedding locally (no image leaves the
    device) and submits the raw 512-vector to be stored as the user's template
    via the SAME dual-column Fernet path that the image ``/enroll`` path uses
    after it computes the embedding.

    SECURITY: this path has NO image, so liveness / anti-spoof is NOT performed
    here. The Identity Core layer (sub-projects B/C) must pair it with a
    liveness factor before trusting the enrollment.
    """

    tenant_id: str = Field(..., description="Tenant identifier for multi-tenancy")
    user_id: str = Field(..., description="User identifier to enroll")
    embedding: List[float] = Field(
        ...,
        description=(
            f"Precomputed {EMBEDDING_DIMENSION}-d Facenet512 embedding, "
            "L2-normalized by the client. Must be exactly "
            f"{EMBEDDING_DIMENSION} floats."
        ),
    )

    @field_validator("embedding")
    @classmethod
    def _validate_embedding_length(cls, value: List[float]) -> List[float]:
        if len(value) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"embedding must have exactly {EMBEDDING_DIMENSION} elements, "
                f"got {len(value)}"
            )
        return value


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
