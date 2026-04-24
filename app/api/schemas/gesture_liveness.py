"""Schemas for active gesture liveness (landmarks-only, server-side).

Design note
-----------
MediaPipe hand inference runs CLIENT-SIDE. The server accepts 21-point hand
landmark arrays plus anti-spoof scores (tremor variance, brightness std) and
runs deterministic geometry + DTW checks. No ML inference happens server-side,
so no MediaPipe / TFLite runtime is loaded here.

Landmark ordering follows the MediaPipe Hand Landmarker schema:
    0=WRIST, 1-4=THUMB (CMC/MCP/IP/TIP),
    5-8=INDEX (MCP/PIP/DIP/TIP), 9-12=MIDDLE, 13-16=RING, 17-20=PINKY.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.active_liveness import ActiveLivenessConfig, ChallengeType


# MediaPipe Hand Landmarker emits exactly 21 points per hand.
HAND_LANDMARK_COUNT: int = 21


class GestureChallengeType(str, Enum):
    """Gesture challenges supported by the server verifier.

    String values deliberately match the gesture-modality entries on
    :class:`app.api.schemas.active_liveness.ChallengeType` so a
    ``Challenge.type`` enum instance can be mapped to either symbol.
    """

    FINGER_COUNT = "finger_count"
    SHAPE_TRACE = "shape_trace"
    WAVE = "wave"
    HAND_FLIP = "hand_flip"
    FINGER_TAP = "finger_tap"
    PINCH = "pinch"
    PEEK_A_BOO = "peek_a_boo"
    MATH = "math"
    HOLD_POSITION = "hold_position"


# Mapping so use cases that carry the parent `ChallengeType` can route
# gesture-typed challenges to the gesture manager without extra plumbing.
_GESTURE_CHALLENGE_VALUE_SET: frozenset[str] = frozenset(
    {
        GestureChallengeType.FINGER_COUNT.value,
        GestureChallengeType.SHAPE_TRACE.value,
        GestureChallengeType.WAVE.value,
        GestureChallengeType.HAND_FLIP.value,
        GestureChallengeType.FINGER_TAP.value,
        GestureChallengeType.PINCH.value,
        GestureChallengeType.PEEK_A_BOO.value,
        GestureChallengeType.MATH.value,
        GestureChallengeType.HOLD_POSITION.value,
    }
)


def is_gesture_challenge(challenge_type: ChallengeType | GestureChallengeType | str) -> bool:
    """Return True if the challenge is a gesture-modality challenge."""

    if isinstance(challenge_type, GestureChallengeType):
        return True
    value = challenge_type.value if isinstance(challenge_type, Enum) else str(challenge_type)
    return value in _GESTURE_CHALLENGE_VALUE_SET


def to_gesture_challenge_type(
    challenge_type: ChallengeType | GestureChallengeType | str,
) -> GestureChallengeType:
    """Coerce a ChallengeType/str to GestureChallengeType, raising if unsupported."""

    if isinstance(challenge_type, GestureChallengeType):
        return challenge_type
    value = challenge_type.value if isinstance(challenge_type, Enum) else str(challenge_type)
    return GestureChallengeType(value)


GESTURE_CHALLENGE_INSTRUCTIONS: dict[GestureChallengeType, str] = {
    GestureChallengeType.FINGER_COUNT: "Show the requested number of fingers",
    GestureChallengeType.SHAPE_TRACE: "Trace the shape shown on screen with your index finger",
    GestureChallengeType.WAVE: "Wave your hand side to side",
    GestureChallengeType.HAND_FLIP: "Flip your hand to show the back and then the palm",
    GestureChallengeType.FINGER_TAP: "Tap your index and middle fingertips together",
    GestureChallengeType.PINCH: "Pinch your thumb and index finger together",
    GestureChallengeType.PEEK_A_BOO: "Cover your face with your hand, then reveal it",
    GestureChallengeType.MATH: "Show the number of fingers that answers the question",
    GestureChallengeType.HOLD_POSITION: "Hold your hand still in the target position",
}


def get_gesture_challenge_instruction(challenge_type: GestureChallengeType) -> str:
    return GESTURE_CHALLENGE_INSTRUCTIONS.get(
        challenge_type, f"Please perform: {challenge_type.value}"
    )


class HandLandmark(BaseModel):
    """Single normalised hand landmark (MediaPipe Hand Landmarker output).

    x, y are normalised to the camera frame in [0, 1]; z is relative depth
    (negative = towards the camera). Values outside [-2, 2] are clipped by
    the validator below to defend against malformed/hostile payloads.
    """

    x: float = Field(..., description="Normalised x in [0, 1] (camera frame).")
    y: float = Field(..., description="Normalised y in [0, 1] (camera frame).")
    z: float = Field(..., description="Relative depth; MediaPipe sign convention.")

    @field_validator("x", "y", "z")
    @classmethod
    def _clip_range(cls, value: float) -> float:
        if not isinstance(value, (int, float)):
            raise TypeError("landmark coordinate must be numeric")
        # MediaPipe rarely reports values outside [-1.5, 1.5]; anything
        # beyond +/-2 is almost certainly a crafted payload.
        if value != value:  # NaN guard
            raise ValueError("landmark coordinate is NaN")
        if value < -2.0 or value > 2.0:
            raise ValueError(
                f"landmark coordinate {value!r} outside the accepted [-2, 2] range"
            )
        return float(value)


class GestureFramePayload(BaseModel):
    """One frame's worth of hand landmarks + anti-spoof telemetry.

    Either ``landmarks_left`` or ``landmarks_right`` MUST be non-null (or both);
    a frame with neither is rejected. ``client_verdict`` is optional and is
    used only as a UX hint — server verdicts are authoritative.
    """

    frame_time_ms: int = Field(
        ...,
        ge=0,
        description="Monotonic client timestamp in milliseconds since session start.",
    )
    landmarks_left: Optional[List[HandLandmark]] = Field(
        default=None,
        description="21 landmarks for the LEFT hand, or null if absent.",
    )
    landmarks_right: Optional[List[HandLandmark]] = Field(
        default=None,
        description="21 landmarks for the RIGHT hand, or null if absent.",
    )
    tremor_variance: float = Field(
        ...,
        ge=0.0,
        description=(
            "Client-measured std-dev of wrist position across a short sliding "
            "window. Server rejects frames where this is suspiciously low."
        ),
    )
    brightness_std: float = Field(
        ...,
        ge=0.0,
        description=(
            "Client-measured std-dev of hand-region brightness. Zero variance "
            "= static image / frozen video; server rejects such frames."
        ),
    )
    client_verdict: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Optional client-side optimistic classification ('detected', "
            "'pending', 'low_confidence', ...). Informational only."
        ),
    )
    face_covered: Optional[bool] = Field(
        default=None,
        description=(
            "Client hint for the PEEK_A_BOO challenge: true if the hand is "
            "currently occluding the face. Server verifies monotonicity across "
            "frames; a single-frame flag alone is not trusted."
        ),
    )

    @field_validator("landmarks_left", "landmarks_right")
    @classmethod
    def _require_full_hand(cls, value: Optional[List[HandLandmark]]) -> Optional[List[HandLandmark]]:
        if value is None:
            return value
        if len(value) != HAND_LANDMARK_COUNT:
            raise ValueError(
                f"hand landmark list must have exactly {HAND_LANDMARK_COUNT} points "
                f"(got {len(value)})"
            )
        return value


class GestureLivenessConfig(ActiveLivenessConfig):
    """Session config for gesture liveness.

    Inherits the base ActiveLivenessConfig fields (num_challenges, timeouts,
    randomize, session_timeout_seconds). ``required_gesture_challenges`` is a
    gesture-typed analogue of ``required_challenges`` on the base config.
    """

    required_gesture_challenges: Optional[List[GestureChallengeType]] = Field(
        default=None,
        description="Specific gesture challenges to include (overrides random).",
    )
    target_finger_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description=(
            "Target finger count for FINGER_COUNT / MATH challenges. If None, "
            "the server picks one at random."
        ),
    )


class GestureSessionStartRequest(GestureLivenessConfig):
    """Request body for POST /liveness/active/gesture/start."""


class ShapeTemplate(BaseModel):
    """A single shape template served to clients for SHAPE_TRACE challenges."""

    key: Literal["circle", "square", "triangle", "s_curve"]
    label: str
    svg_path: str = Field(..., description="SVG path string in a 0..1 unit viewBox.")
    points: List[List[float]] = Field(
        ...,
        description="Sampled (x, y) points along the path, normalised to [0, 1].",
    )
    min_trace_points: int = Field(default=25, ge=5)


class ShapeTemplateCatalog(BaseModel):
    """Wrapper returned by GET /liveness/active/gesture/shape-templates."""

    version: str = Field(..., description="Opaque ETag-style version string (mtime-based).")
    templates: List[ShapeTemplate]


__all__ = [
    "HAND_LANDMARK_COUNT",
    "GestureChallengeType",
    "GESTURE_CHALLENGE_INSTRUCTIONS",
    "get_gesture_challenge_instruction",
    "is_gesture_challenge",
    "to_gesture_challenge_type",
    "HandLandmark",
    "GestureFramePayload",
    "GestureLivenessConfig",
    "GestureSessionStartRequest",
    "ShapeTemplate",
    "ShapeTemplateCatalog",
]
