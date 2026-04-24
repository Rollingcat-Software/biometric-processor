"""Schemas for active liveness detection with challenge sessions."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChallengeType(str, Enum):
    """Types of liveness challenges.

    Face-modality values (``BLINK`` … ``RAISE_EYEBROWS``) are scored by
    ``ActiveLivenessManager`` against MediaPipe face landmarks.
    Gesture-modality values (``FINGER_COUNT`` … ``HOLD_POSITION``) are scored
    by ``ActiveGestureLivenessManager`` against client-supplied hand landmarks.
    Mirror of ``GestureChallengeType`` in ``app.api.schemas.gesture_liveness``;
    the two enums share string values so ``Challenge.type`` can store either.
    """

    # Face modality
    BLINK = "blink"
    SMILE = "smile"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    NOD = "nod"
    OPEN_MOUTH = "open_mouth"
    RAISE_EYEBROWS = "raise_eyebrows"
    # Gesture modality (server-side verifies landmarks-only; no ML inference).
    FINGER_COUNT = "finger_count"
    SHAPE_TRACE = "shape_trace"
    WAVE = "wave"
    HAND_FLIP = "hand_flip"
    FINGER_TAP = "finger_tap"
    PINCH = "pinch"
    PEEK_A_BOO = "peek_a_boo"
    MATH = "math"
    HOLD_POSITION = "hold_position"


class ChallengeStatus(str, Enum):
    """Status of a challenge."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Challenge(BaseModel):
    """A single liveness challenge."""

    type: ChallengeType = Field(..., description="Type of challenge")
    instruction: str = Field(..., description="Human-readable instruction")
    status: ChallengeStatus = Field(default=ChallengeStatus.PENDING)
    timeout_seconds: float = Field(default=5.0, description="Time to complete challenge")
    attempts: int = Field(default=0, description="Number of attempts")
    max_attempts: int = Field(default=3, description="Maximum attempts allowed")
    confidence: float = Field(default=0.0, description="Detection confidence when completed")


class ActiveLivenessConfig(BaseModel):
    """Configuration for an active liveness session."""

    num_challenges: int = Field(default=3, ge=1, le=5, description="Number of challenges")
    challenge_timeout: float = Field(default=5.0, gt=0, description="Seconds per challenge")
    randomize: bool = Field(default=True, description="Randomize challenge order")
    session_timeout_seconds: float = Field(default=120.0, gt=0, description="Session time-to-live")
    required_challenges: Optional[List[ChallengeType]] = Field(
        default=None,
        description="Specific challenges to include",
    )


class ActiveLivenessStartRequest(ActiveLivenessConfig):
    """Request body for starting a session."""


class ActiveLivenessSession(BaseModel):
    """Active liveness session state.

    ``modality`` defaults to ``"face"`` for back-compat with the existing
    face-liveness flow. When ``"gesture"``, the session is scored by
    ``ActiveGestureLivenessManager`` using client-supplied hand landmarks
    rather than server-side MediaPipe inference.
    """

    session_id: str = Field(..., description="Unique session ID")
    modality: Literal["face", "gesture"] = Field(
        default="face",
        description="Liveness modality. 'face' = legacy face landmarks; 'gesture' = hand landmarks.",
    )
    challenges: List[Challenge] = Field(default_factory=list)
    current_challenge_index: int = Field(default=0)
    started_at: float = Field(..., description="Unix timestamp when the session started")
    expires_at: float = Field(..., description="Unix timestamp when the session expires")
    last_activity_at: float = Field(..., description="Unix timestamp of the last session activity")
    current_challenge_started_at: float = Field(..., description="Unix timestamp for the current challenge")
    completed_at: Optional[float] = Field(default=None)
    is_complete: bool = Field(default=False)
    passed: bool = Field(default=False)
    overall_score: float = Field(default=0.0)
    baseline_ear: Optional[float] = Field(default=None)
    baseline_mar: Optional[float] = Field(default=None)
    blink_detected: bool = Field(default=False)
    last_ear: float = Field(default=0.3)
    # Gesture-modality working state (ignored when modality == "face").
    gesture_state: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Per-session scratch state for gesture liveness. Stores wrist "
            "trajectories, frame counts, palm-normal history, etc. Only "
            "populated when modality == 'gesture'."
        ),
    )


class ChallengeResult(BaseModel):
    """Result of a challenge detection."""

    challenge_type: ChallengeType
    detected: bool = Field(..., description="Whether the action was detected")
    confidence: float = Field(default=0.0, ge=0, le=1)
    details: Dict[str, Any] = Field(default_factory=dict)


class ActiveLivenessResponse(BaseModel):
    """Response for active liveness session state and frame analysis."""

    session_id: Optional[str] = Field(default=None, description="Active liveness session ID")
    current_challenge: Optional[Challenge] = None
    challenge: Optional[Challenge] = None
    challenge_progress: float = Field(default=0.0, description="Progress 0-1")
    time_remaining: float = Field(default=0.0, description="Seconds remaining")
    detection: Optional[ChallengeResult] = None
    challenges_completed: int = Field(default=0)
    challenges_total: int = Field(default=0)
    session_complete: bool = Field(default=False)
    session_passed: bool = Field(default=False)
    overall_score: float = Field(default=0.0)
    instruction: str = Field(default="", description="Current instruction to display")
    feedback: str = Field(default="", description="Feedback on user's action")


CHALLENGE_INSTRUCTIONS = {
    ChallengeType.BLINK: "Please blink your eyes",
    ChallengeType.SMILE: "Please smile",
    ChallengeType.TURN_LEFT: "Please turn your head to the left",
    ChallengeType.TURN_RIGHT: "Please turn your head to the right",
    ChallengeType.NOD: "Please nod your head",
    ChallengeType.OPEN_MOUTH: "Please open your mouth wide",
    ChallengeType.RAISE_EYEBROWS: "Please raise your eyebrows",
    # Gesture modality
    ChallengeType.FINGER_COUNT: "Show the requested number of fingers",
    ChallengeType.SHAPE_TRACE: "Trace the shape with your index finger",
    ChallengeType.WAVE: "Wave your hand side to side",
    ChallengeType.HAND_FLIP: "Flip your hand to show the back and then the palm",
    ChallengeType.FINGER_TAP: "Tap your index and middle fingertips together",
    ChallengeType.PINCH: "Pinch your thumb and index finger together",
    ChallengeType.PEEK_A_BOO: "Cover your face with your hand, then reveal it",
    ChallengeType.MATH: "Show the number of fingers that answers the question",
    ChallengeType.HOLD_POSITION: "Hold your hand still in the target position",
}


def get_challenge_instruction(challenge_type: ChallengeType) -> str:
    """Get the instruction for a challenge type."""

    return CHALLENGE_INSTRUCTIONS.get(challenge_type, f"Please perform: {challenge_type.value}")
