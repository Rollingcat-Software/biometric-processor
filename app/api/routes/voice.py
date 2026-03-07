"""Stub endpoints for voice biometric processing."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Voice"])


class VoiceRequest(BaseModel):
    user_id: str
    voice_data: str


class BiometricStubResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None


@router.post("/voice/enroll")
async def enroll_voice(request: VoiceRequest):
    """Stub endpoint for voice enrollment. Not yet implemented."""
    return BiometricStubResponse(
        success=False,
        message="Voice biometric processing is not yet available. This service currently supports face biometrics only.",
        user_id=request.user_id,
        confidence=0.0,
    )


@router.post("/voice/verify")
async def verify_voice(request: VoiceRequest):
    """Stub endpoint for voice verification. Not yet implemented."""
    return BiometricStubResponse(
        success=False,
        message="Voice biometric processing is not yet available. This service currently supports face biometrics only.",
        user_id=request.user_id,
        confidence=0.0,
    )


@router.delete("/voice/{user_id}")
async def delete_voice(user_id: str):
    """Stub endpoint for voice data deletion. Not yet implemented."""
    return BiometricStubResponse(
        success=True,
        message="No voice data to delete. Voice processing is not yet available.",
        user_id=user_id,
    )
