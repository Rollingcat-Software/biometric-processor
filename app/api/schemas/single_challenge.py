"""Schema for single-challenge server validation (Bug 4, 2026-05-12).

The web biometric-puzzles training surface (``BiometricPuzzlesPage``) runs
one challenge at a time with local MediaPipe detection. Before this fix, it
called ``onSuccess`` purely client-side — anyone could trivially mock the
component and "pass" the puzzle. This schema is for the new
``/liveness/verify-challenge`` endpoint that records a server round-trip
for each completed challenge and returns a server verdict.

The contract is intentionally narrow:
  * One action per request.
  * Client supplies start/end timestamps and a detection confidence
    derived from MediaPipe.
  * Server runs the cheap structural validations (action is a known type,
    timestamps are monotonic and within a reasonable window, confidence
    above a floor) and returns a verdict.

Heavier server-side detection (re-running MediaPipe on uploaded frames) is
out of scope for the training surface — the deep validation belongs to
multi-step ``/liveness/verify`` flows used by enrollment.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.api.schemas.active_liveness import ChallengeType


class VerifyChallengeRequest(BaseModel):
    """Single challenge completion record submitted by the web client."""

    action: ChallengeType = Field(
        ..., description="The completed challenge action (e.g. blink, smile, pinch)."
    )
    start_timestamp_ms: float = Field(
        ...,
        gt=0,
        description=(
            "Client clock (performance.now() base or unix-ms) when the "
            "challenge started. Used for monotonicity + duration sanity."
        ),
    )
    end_timestamp_ms: float = Field(
        ...,
        gt=0,
        description="Client clock when the challenge was detected as completed.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detection confidence reported by the client engine [0..1].",
    )
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier.")
    user_id: Optional[str] = Field(default=None, description="User identifier.")
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional metric payload (e.g. min_ear for blink, mar_ratio for "
            "smile, finger_count for hand puzzles). Logged for audit, never "
            "used as the sole pass/fail signal."
        ),
    )


class VerifyChallengeResponse(BaseModel):
    """Server verdict for a single challenge submission."""

    verified: bool = Field(..., description="Whether the challenge passed.")
    action: ChallengeType = Field(..., description="The echoed challenge action.")
    duration_seconds: float = Field(
        ..., ge=0.0, description="end - start, in seconds (post-validation)."
    )
    reason_code: Optional[str] = Field(
        default=None,
        description=(
            "Failure category when ``verified=false`` "
            "(e.g. TIMESTAMPS_OUT_OF_ORDER, DURATION_TOO_SHORT, "
            "CONFIDENCE_BELOW_FLOOR, UNKNOWN_ACTION)."
        ),
    )
    message: str = Field(default="", description="Human-readable result message.")
