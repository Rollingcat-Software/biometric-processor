"""Stub endpoints for fingerprint biometric processing."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Fingerprint"])


class FingerprintRequest(BaseModel):
    user_id: str
    fingerprint_data: str


class BiometricStubResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None


@router.post("/fingerprint/enroll")
async def enroll_fingerprint(request: FingerprintRequest):
    """Stub endpoint for fingerprint enrollment. Not yet implemented."""
    return BiometricStubResponse(
        success=False,
        message="Fingerprint biometric processing is not yet available. This service currently supports face biometrics only.",
        user_id=request.user_id,
        confidence=0.0,
    )


@router.post("/fingerprint/verify")
async def verify_fingerprint(request: FingerprintRequest):
    """Stub endpoint for fingerprint verification. Not yet implemented."""
    return BiometricStubResponse(
        success=False,
        message="Fingerprint biometric processing is not yet available. This service currently supports face biometrics only.",
        user_id=request.user_id,
        confidence=0.0,
    )


@router.delete("/fingerprint/{user_id}")
async def delete_fingerprint(user_id: str):
    """Stub endpoint for fingerprint data deletion. Not yet implemented."""
    return BiometricStubResponse(
        success=True,
        message="No fingerprint data to delete. Fingerprint processing is not yet available.",
        user_id=user_id,
    )
