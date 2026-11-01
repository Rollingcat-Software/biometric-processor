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

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

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
    require_identity_binding: Optional[bool] = Field(
        default=None,
        description=(
            "Whether the verdict may require the v2 binding-frame consistency "
            "check. false = the per-challenge face windows are not retained (a "
            "later binding-required verdict fails closed). Omitted = retained "
            "(backward compatible)."
        ),
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
    trace_contract: Optional[str] = Field(
        default=None,
        description=(
            "Contract v2 advertisement. 'v2' when PUZZLE_TRACE_V2_ENABLED is on: "
            "every SUBMIT must carry a landmark `trace` (scalar-only metrics are "
            "rejected with TRACE_REQUIRED) and challenges must be submitted in "
            "the issued order. Absent (null) on the legacy v1 scalar path."
        ),
    )
    trace_face_indices: Optional[List[int]] = Field(
        default=None,
        description=(
            "v2 only: the MediaPipe 478-mesh indices a face trace frame must "
            "carry, in wire order (x,y,z per index, ints in 1e-4 units)."
        ),
    )


_TRACE_COORD_ABS_MAX = 20_000  # |normalised coord| <= 2.0 in 1e-4 units
_FACE_TRACE_INTS = 32 * 3
_HAND_TRACE_INTS = 21 * 3
_MAX_TRACE_FRAMES = 200


def _check_coords(values: Optional[List[int]], expected: int, name: str) -> Optional[List[int]]:
    if values is None:
        return None
    if len(values) != expected:
        raise ValueError(f"{name} must carry exactly {expected} ints")
    if values and (max(values) > _TRACE_COORD_ABS_MAX or min(values) < -_TRACE_COORD_ABS_MAX):
        raise ValueError(f"{name} coordinate outside the accepted range")
    return values


class PuzzleTraceFrame(BaseModel):
    """One timestamped frame of a v2 landmark trace (compact wire form)."""

    t: int = Field(..., ge=0, le=2**53, description="Client clock (performance.now) in ms.")
    f: Optional[List[int]] = Field(
        default=None,
        description="Face: 32 landmarks (trace_face_indices order) as flat x,y,z ints (1e-4 units).",
    )
    h: Optional[List[int]] = Field(
        default=None,
        description="Hand: 21 MediaPipe hand landmarks as flat x,y,z ints, or null when no hand is visible.",
    )

    @field_validator("f")
    @classmethod
    def _face_len(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        return _check_coords(v, _FACE_TRACE_INTS, "f")

    @field_validator("h")
    @classmethod
    def _hand_len(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        return _check_coords(v, _HAND_TRACE_INTS, "h")


class PuzzleTrace(BaseModel):
    """Contract v2: the raw landmark trace the server re-scores."""

    version: Literal[2] = Field(..., description="Trace contract version (2).")
    frame_width: int = Field(..., ge=64, le=8192, description="Video frame width in px.")
    frame_height: int = Field(..., ge=64, le=8192, description="Video frame height in px.")
    frames: List[PuzzleTraceFrame] = Field(
        ..., min_length=1, max_length=_MAX_TRACE_FRAMES, description="Frames in capture order."
    )


class PuzzleBindingFrame(BaseModel):
    """v2 binding-frame consistency check: the client-DECLARED frame the identity
    embedding came from. Only checked against the client's own trace; it does
    not tie the embedding to the live capture (a modified client can pass it)."""

    t: int = Field(..., ge=0, le=2**53, description="Client clock (same timebase as traces), ms.")
    f: List[int] = Field(..., description="32 face landmarks, same encoding as a trace frame.")

    @field_validator("f")
    @classmethod
    def _face_len(cls, v: List[int]) -> List[int]:
        out = _check_coords(v, _FACE_TRACE_INTS, "f")
        assert out is not None
        return out


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
    trace: Optional[PuzzleTrace] = Field(
        default=None,
        description=(
            "Contract v2 landmark trace. REQUIRED when the session advertises "
            "trace_contract='v2' (the server recomputes the metric from it and "
            "ignores `metrics`); ignored on the legacy v1 path."
        ),
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
    require_identity_binding: bool = Field(
        default=False,
        description=(
            "Set by identity-core-api when the PUZZLE step also matches face "
            "identity (alsoMatchFaceIdentity). Under contract v2 the verdict "
            "then additionally requires a valid `binding_frame`."
        ),
    )
    binding_frame: Optional[PuzzleBindingFrame] = Field(
        default=None,
        description=(
            "v2: landmarks + timestamp of the frame the identity embedding was "
            "computed from (client-declared, forwarded by identity-core-api)."
        ),
    )


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
    binding_checked: Optional[bool] = Field(
        default=None,
        description=(
            "Version handshake. true only when require_identity_binding was set, "
            "the session is contract v2 and the binding-frame consistency check "
            "was evaluated and passed. Omitted otherwise (always omitted on v1), so "
            "a caller that requires binding can fail closed when it is absent."
        ),
    )


__all__ = [
    "PuzzleSessionCreateRequest",
    "PuzzleSessionCreateResponse",
    "IssuedChallenge",
    "PuzzleTrace",
    "PuzzleTraceFrame",
    "PuzzleBindingFrame",
    "PuzzleSessionChallengeRequest",
    "PuzzleSessionChallengeResponse",
    "PuzzleSessionVerdictRequest",
    "PuzzleSessionVerdictResponse",
]
