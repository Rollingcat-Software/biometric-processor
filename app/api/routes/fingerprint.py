"""Stub endpoints for fingerprint biometric processing.

These endpoints exist so that identity-core-api's BiometricServiceAdapter
gets a clear HTTP 501 Not Implemented response instead of a misleading
success=false at HTTP 200. Callers must distinguish between
"biometric mismatch" (200 + success=false) and "feature unavailable" (501).

Fingerprint server-side processing is not implemented. The correct
architecture for mobile fingerprint auth is device-side biometric
(TouchID/FaceID) via the step-up ECDSA P-256 challenge-response flow.

See TODO.md BIO-1 and ROADMAP.md Phase 4 for implementation plans.
"""

from fastapi import APIRouter, HTTPException
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


@router.post("/fingerprint/enroll", status_code=501)
async def enroll_fingerprint(request: FingerprintRequest) -> BiometricResponse:
    """Fingerprint enrollment — NOT IMPLEMENTED.

    Returns HTTP 501 so callers can distinguish this from a real biometric
    failure (HTTP 200 + success=false). Use the step-up ECDSA P-256 flow
    for device-native fingerprint authentication instead.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "success": False,
            "modality": "fingerprint",
            "implemented": False,
            "message": (
                "Fingerprint server-side processing is not implemented. "
                "Use the step-up challenge-response flow (/api/v1/step-up/*) "
                "for device-native biometric authentication."
            ),
        },
    )


@router.post("/fingerprint/verify", status_code=501)
async def verify_fingerprint(request: FingerprintRequest) -> BiometricResponse:
    """Fingerprint verification — NOT IMPLEMENTED.

    Returns HTTP 501. See enroll_fingerprint for alternative.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "success": False,
            "modality": "fingerprint",
            "implemented": False,
            "message": (
                "Fingerprint verification is not implemented. "
                "Use the step-up challenge-response flow (/api/v1/step-up/*) "
                "for device-native biometric authentication."
            ),
        },
    )


@router.delete("/fingerprint/{user_id}")
async def delete_fingerprint(user_id: str) -> BiometricResponse:
    """Fingerprint data deletion — no-op (nothing stored)."""
    return BiometricResponse(
        success=True,
        message="No fingerprint data stored. Server-side fingerprint processing is not implemented.",
        user_id=user_id,
    )
