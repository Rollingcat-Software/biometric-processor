"""Common API schemas."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response format.

    All API errors return this consistent structure.
    """

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error_code": "FACE_NOT_DETECTED",
                "message": "No face detected in the image",
                "details": None,
            }
        }
    }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    model: str = Field(..., description="Face recognition model in use")
    detector: str = Field(..., description="Face detector in use")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "model": "Facenet",
                "detector": "opencv",
            }
        }
    }
