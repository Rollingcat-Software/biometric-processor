"""Verification API schemas."""

from typing import Any, Optional

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
    device_spoof_risk: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional device-spoof risk breakdown from DeviceSpoofRiskEvaluator. "
            "Populated only when ANTISPOOF_DEVICE_RISK_ENABLED=true. Informational; "
            "never blocks verification."
        ),
    )
    antispoof_pipeline: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional combined verdict from spoof_detector.pipeline.AntispoofPipelineAssembler. "
            "Populated only when at least one of ANTISPOOF_USABILITY_GATE_ENABLED / "
            "ANTISPOOF_FUSION_ENABLED is true. The `recommended_action` is advisory; "
            "this service never enforces it."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "verified": True,
                "confidence": 0.87,
                "distance": 0.13,
                "threshold": 0.6,
                "message": "Face verified successfully",
                "device_spoof_risk": None,
                "antispoof_pipeline": None,
            }
        }
    }
