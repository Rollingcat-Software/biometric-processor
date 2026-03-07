"""Stub endpoints for fingerprint biometric processing.

These endpoints exist so that identity-core-api's BiometricServiceAdapter
gets structured error responses instead of 404s. Fingerprint biometric
processing is not yet implemented - consider using WebAuthn platform
authenticators (Touch ID, Windows Hello) as an alternative.

See TODO.md BIO-1 and ROADMAP.md Phase 2 for implementation plans.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Fingerprint"])


class FingerprintRequest(BaseModel):
    user_id: str
    fingerprint_data: str


class BiometricResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    modality: str = "fingerprint"
    implemented: bool = False


@router.post("/fingerprint/enroll")
async def enroll_fingerprint(request: FingerprintRequest) -> BiometricResponse:
    """Stub endpoint for fingerprint enrollment.

    Returns a structured error response indicating this modality is not yet
    implemented. The identity-core-api's FingerprintAuthHandler calls this
    endpoint via BiometricServiceAdapter.enrollFingerprint().

    Alternative: Use WebAuthn platform authenticators for fingerprint
    authentication without server-side biometric processing.
    """
    return BiometricResponse(
        success=False,
        message=(
            "Fingerprint biometric processing is not yet implemented. "
            "Consider using WebAuthn platform authenticators (Touch ID, Windows Hello) "
            "as an alternative for fingerprint-based authentication."
        ),
        user_id=request.user_id,
        confidence=0.0,
    )


@router.post("/fingerprint/verify")
async def verify_fingerprint(request: FingerprintRequest) -> BiometricResponse:
    """Stub endpoint for fingerprint verification.

    Returns a structured error response. The identity-core-api's
    FingerprintAuthHandler calls this via BiometricServiceAdapter.verifyFingerprint().
    """
    return BiometricResponse(
        success=False,
        message=(
            "Fingerprint biometric verification is not yet implemented. "
            "This modality requires either a fingerprint SDK integration "
            "or migration to WebAuthn platform authenticators."
        ),
        user_id=request.user_id,
        confidence=0.0,
    )


@router.delete("/fingerprint/{user_id}")
async def delete_fingerprint(user_id: str) -> BiometricResponse:
    """Stub endpoint for fingerprint data deletion."""
    return BiometricResponse(
        success=True,
        message="No fingerprint data to delete. Fingerprint processing is not yet implemented.",
        user_id=user_id,
    )
