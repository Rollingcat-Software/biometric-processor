"""Flash / colour-light liveness challenge route.

Public, stateless wrapper around `LightChallengeService` that lets a client
(web/mobile) request a challenge colour, then submit a frame captured during
the on-screen flash for verification. The handler is intentionally
thin — the underlying service is already production-grade and consumed by
`active_liveness_manager` and `device_spoof_risk_evaluator`.

Endpoints:
    POST /flash-challenge/start    — issue a fresh challenge
    POST /flash-challenge/respond  — verify a captured frame against challenge

This route is **not** enabled by default; the FLASH_CHALLENGE_ROUTE_ENABLED
flag in settings gates registration so prod stays unchanged until an operator
opts in.
"""

from __future__ import annotations

import base64
import logging
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.services.light_challenge_service import LightChallengeService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Liveness"], prefix="/liveness")

# Single shared service; stateless aside from RNG / config.
_service = LightChallengeService()


class FlashChallengeStartResponse(BaseModel):
    color: str = Field(..., description="Colour the client must flash on the screen")
    available_colors: List[str]
    issued_at: float
    expires_at: float
    duration_ms: int
    expected_response_window_ms: int
    minimum_delay_ms: int
    baseline_required: bool
    ready_for_flash: bool


class FlashChallengeRespondRequest(BaseModel):
    expected_color: str = Field(..., description="Colour returned by /start")
    flash_timestamp: float = Field(..., description="Unix epoch when the flash was rendered")
    frame_timestamp: Optional[float] = Field(
        None,
        description="Unix epoch when the frame was captured; defaults to server time if omitted",
    )
    frame_base64: str = Field(..., description="Base64-encoded JPEG/PNG frame captured during flash")
    baseline_bgr: Optional[List[float]] = Field(
        None,
        description="Optional pre-flash baseline BGR mean (length 3); strengthens detection",
    )


class FlashChallengeRespondResponse(BaseModel):
    passed: bool
    reason: Optional[str] = None
    color_shift: Optional[float] = None
    delay_seconds: Optional[float] = None
    face_mean_bgr: Optional[List[float]] = None


@router.post("/flash-challenge/start", response_model=FlashChallengeStartResponse)
async def start_flash_challenge() -> FlashChallengeStartResponse:
    """Issue a fresh flash-colour challenge."""
    challenge = _service.generate_challenge()
    return FlashChallengeStartResponse(**challenge)


@router.post("/flash-challenge/respond", response_model=FlashChallengeRespondResponse)
async def respond_flash_challenge(payload: FlashChallengeRespondRequest) -> FlashChallengeRespondResponse:
    """Verify a captured frame against a previously issued challenge."""
    if payload.expected_color not in _service._colors:  # noqa: SLF001
        raise HTTPException(status_code=400, detail="unsupported_color")

    try:
        frame_bytes = base64.b64decode(payload.frame_base64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_base64") from exc

    if not frame_bytes:
        raise HTTPException(status_code=400, detail="empty_frame")

    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None or frame.size == 0:
        raise HTTPException(status_code=400, detail="undecodable_frame")

    if payload.baseline_bgr is not None and len(payload.baseline_bgr) != 3:
        raise HTTPException(status_code=400, detail="baseline_bgr_must_be_length_3")

    result = _service.verify_response(
        frame=frame,
        expected_color=payload.expected_color,
        flash_timestamp=payload.flash_timestamp,
        frame_timestamp=payload.frame_timestamp,
        baseline_bgr=payload.baseline_bgr,
    )
    return FlashChallengeRespondResponse(**result)
