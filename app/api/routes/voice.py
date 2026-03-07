"""Stub endpoints for voice biometric processing.

These endpoints exist so that identity-core-api's BiometricServiceAdapter
gets structured error responses instead of 404s. Voice biometric processing
is not yet implemented - requires a speaker verification ML model
(e.g., SpeechBrain, Resemblyzer).

See TODO.md BIO-2 and ROADMAP.md Phase 2 for implementation plans.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Voice"])


class VoiceRequest(BaseModel):
    user_id: str
    voice_data: str


class BiometricResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    modality: str = "voice"
    implemented: bool = False


@router.post("/voice/enroll")
async def enroll_voice(request: VoiceRequest) -> BiometricResponse:
    """Stub endpoint for voice enrollment.

    Returns a structured error response indicating this modality is not yet
    implemented. The identity-core-api's VoiceAuthHandler calls this endpoint
    via BiometricServiceAdapter.enrollVoice().

    Implementation requires: SpeechBrain or Resemblyzer for speaker embeddings,
    voice activity detection, and anti-spoofing measures.
    """
    return BiometricResponse(
        success=False,
        message=(
            "Voice biometric processing is not yet implemented. "
            "Requires speaker verification ML model integration "
            "(SpeechBrain or Resemblyzer recommended)."
        ),
        user_id=request.user_id,
        confidence=0.0,
    )


@router.post("/voice/verify")
async def verify_voice(request: VoiceRequest) -> BiometricResponse:
    """Stub endpoint for voice verification.

    Returns a structured error response. The identity-core-api's
    VoiceAuthHandler calls this via BiometricServiceAdapter.verifyVoice().
    """
    return BiometricResponse(
        success=False,
        message=(
            "Voice biometric verification is not yet implemented. "
            "This modality requires speaker verification ML model integration."
        ),
        user_id=request.user_id,
        confidence=0.0,
    )


@router.delete("/voice/{user_id}")
async def delete_voice(user_id: str) -> BiometricResponse:
    """Stub endpoint for voice data deletion."""
    return BiometricResponse(
        success=True,
        message="No voice data to delete. Voice processing is not yet implemented.",
        user_id=user_id,
    )
