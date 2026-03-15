"""Stub endpoints for voice biometric processing.

These endpoints return HTTP 501 Not Implemented so callers can distinguish
"feature unavailable" (501) from a real biometric failure (200 + success=false).

Voice biometric processing requires a speaker verification ML model
(e.g., SpeechBrain, Resemblyzer) which is not yet integrated.

See TODO.md BIO-2 and ROADMAP.md Phase 4 for implementation plans.
"""

from fastapi import APIRouter, HTTPException
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


@router.post("/voice/enroll", status_code=501)
async def enroll_voice(request: VoiceRequest) -> BiometricResponse:
    """Voice enrollment — NOT IMPLEMENTED.

    Returns HTTP 501 so callers can distinguish this from a real biometric
    failure. Requires SpeechBrain or Resemblyzer speaker embedding integration.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "success": False,
            "modality": "voice",
            "implemented": False,
            "message": (
                "Voice biometric processing is not implemented. "
                "Requires speaker verification ML model integration "
                "(SpeechBrain or Resemblyzer)."
            ),
        },
    )


@router.post("/voice/verify", status_code=501)
async def verify_voice(request: VoiceRequest) -> BiometricResponse:
    """Voice verification — NOT IMPLEMENTED.

    Returns HTTP 501. See enroll_voice for details.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "success": False,
            "modality": "voice",
            "implemented": False,
            "message": (
                "Voice verification is not implemented. "
                "Requires speaker verification ML model integration."
            ),
        },
    )


@router.delete("/voice/{user_id}")
async def delete_voice(user_id: str) -> BiometricResponse:
    """Voice data deletion — no-op (nothing stored)."""
    return BiometricResponse(
        success=True,
        message="No voice data stored. Server-side voice processing is not implemented.",
        user_id=user_id,
    )
