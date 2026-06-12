"""Schemas for the server-issued, single-use, anti-replay puzzle SESSION.

CV-1 of the puzzle-as-login convergence
(docs/superpowers/plans/2026-06-12-puzzle-session-convergence.md).

Three routes, snake_case JSON exactly as the canonical contract specifies:

  POST /api/v1/liveness/puzzle-session
    req:  PuzzleSessionCreateRequest  {tenant_id, user_id, allowed_challenge_types, count, difficulty?}
    resp: PuzzleSessionCreateResponse {session_id, challenges:[{action, params?}]}

  POST /api/v1/liveness/puzzle-session/{session_id}/challenge
    req:  PuzzleSessionChallengeRequest  {action, metrics, start_timestamp_ms, end_timestamp_ms, confidence}
    resp: PuzzleSessionChallengeResponse {verified, action, reason_code?}

  POST /api/v1/liveness/puzzle-session/{session_id}/verdict
    req:  PuzzleSessionVerdictRequest  {user_id, tenant_id}
    resp: PuzzleSessionVerdictResponse {verified}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.api.schemas.active_liveness import ChallengeType


class PuzzleSessionCreateRequest(BaseModel):
    """CREATE — start of the PUZZLE step (identity → bio, X-API-Key)."""

    tenant_id: str = Field(..., description="Owning tenant; binds the session.")
    user_id: str = Field(..., description="Owning user; binds the session.")
    allowed_challenge_types: List[ChallengeType] = Field(
        ...,
        min_length=1,
        description=(
            "The challenge types the server may choose from. May mix face and "
            "hand types; the server randomly selects `count` of them."
        ),
    )
    count: int = Field(
        ..., ge=1, le=10, description="How many challenges to issue (server-randomized)."
    )
    difficulty: Optional[str] = Field(
        default=None, description="Optional difficulty hint (easy|standard|hard)."
    )


class IssuedChallenge(BaseModel):
    """One server-issued challenge returned to the client."""

    action: ChallengeType = Field(..., description="The challenge action to perform.")
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional server-issued parameters for the action (e.g. "
            "{'target': 3} for finger_count). Absent when the action takes none."
        ),
    )


class PuzzleSessionCreateResponse(BaseModel):
    """CREATE response — opaque session id + the server-issued challenges."""

    session_id: str = Field(..., description="Unguessable, single-use, short-TTL token.")
    challenges: List[IssuedChallenge] = Field(
        ..., description="The server-randomized challenges to present, in order."
    )


class PuzzleSessionChallengeRequest(BaseModel):
    """SUBMIT one challenge's traces for scoring (metric REQUIRED)."""

    action: ChallengeType = Field(..., description="The completed challenge action.")
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Client-computed metric payload for the action (REQUIRED on this "
            "path; absent/empty → verified=false with reason METRIC_REQUIRED)."
        ),
    )
    start_timestamp_ms: float = Field(
        ..., gt=0, description="Client clock when the challenge started."
    )
    end_timestamp_ms: float = Field(
        ..., gt=0, description="Client clock when the challenge completed."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Client detection confidence [0..1]."
    )


class PuzzleSessionChallengeResponse(BaseModel):
    """SUBMIT verdict for one challenge (per-challenge UX feedback, not the gate)."""

    verified: bool = Field(..., description="Whether this challenge passed.")
    action: ChallengeType = Field(..., description="The echoed challenge action.")
    reason_code: Optional[str] = Field(
        default=None,
        description=(
            "Failure category when verified=false (METRIC_REQUIRED, "
            "ACTION_NOT_ISSUED, ALREADY_COMPLETED, TIMESTAMPS_OUT_OF_ORDER, "
            "CONFIDENCE_BELOW_FLOOR, or an action-specific metric reason)."
        ),
    )


class PuzzleSessionVerdictRequest(BaseModel):
    """VERDICT — the auth gate. Client sends ONLY owner identity."""

    user_id: str = Field(..., description="Requesting user; must match the session owner.")
    tenant_id: str = Field(..., description="Requesting tenant; must match the session owner.")


class PuzzleSessionVerdictResponse(BaseModel):
    """VERDICT result — authoritative pass/fail. Session is consumed on this call."""

    verified: bool = Field(
        ...,
        description=(
            "True iff all issued challenges validated AND owner matches AND not "
            "expired AND not already consumed. The session is single-use: a "
            "second verdict call returns false."
        ),
    )


__all__ = [
    "PuzzleSessionCreateRequest",
    "PuzzleSessionCreateResponse",
    "IssuedChallenge",
    "PuzzleSessionChallengeRequest",
    "PuzzleSessionChallengeResponse",
    "PuzzleSessionVerdictRequest",
    "PuzzleSessionVerdictResponse",
]
