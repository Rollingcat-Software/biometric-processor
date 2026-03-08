"""Schemas for liveness puzzle endpoints (generate-puzzle, verify)."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
import uuid

from app.api.schemas.active_liveness import ChallengeType


class PuzzleDifficulty(str, Enum):
    """Puzzle difficulty levels."""

    EASY = "easy"  # 2-3 steps, 7s per step
    STANDARD = "standard"  # 3-4 steps, 5s per step
    HARD = "hard"  # 4-5 steps, 4s per step


class PuzzleStep(BaseModel):
    """Single step in a liveness puzzle."""

    action: str = Field(..., description="Challenge type (blink, smile, turn_left, etc.)")
    duration_seconds: float = Field(
        default=5.0, ge=2.0, le=30.0, description="Time to complete this step"
    )
    order: int = Field(..., ge=0, description="Step order (0-indexed)")


class GeneratePuzzleRequest(BaseModel):
    """Request to generate a new liveness puzzle."""

    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    difficulty: PuzzleDifficulty = Field(
        default=PuzzleDifficulty.STANDARD, description="Puzzle difficulty level"
    )
    min_steps: int = Field(default=3, ge=2, le=5, description="Minimum number of steps")
    max_steps: int = Field(default=4, ge=3, le=7, description="Maximum number of steps")
    timeout_seconds: int = Field(
        default=60, ge=30, le=300, description="Total puzzle timeout in seconds"
    )


class GeneratePuzzleResponse(BaseModel):
    """Generated puzzle for liveness verification."""

    puzzle_id: str = Field(..., description="Unique puzzle identifier")
    steps: List[PuzzleStep] = Field(..., description="Ordered list of challenge steps")
    timeout_seconds: int = Field(..., description="Total time allowed for puzzle")
    expires_at: datetime = Field(..., description="Puzzle expiration timestamp")
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "ear_threshold": 0.21,
            "mar_threshold": 0.4,
            "head_turn_threshold": 0.15,
            "mouth_open_threshold": 0.5,
            "eyebrow_threshold": 0.08,
        },
        description="Detection thresholds for client-side processing",
    )


class StepEvidence(BaseModel):
    """Evidence for a completed step."""

    action: str = Field(..., description="Challenge action performed")
    start_timestamp: float = Field(..., description="Start time (Unix timestamp)")
    end_timestamp: float = Field(..., description="End time (Unix timestamp)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence (0-1)"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detection metrics (e.g., min_ear, max_mar)",
    )


class ClientMeta(BaseModel):
    """Client metadata for audit purposes."""

    browser: Optional[str] = Field(default=None, description="Browser user agent")
    device: Optional[str] = Field(default=None, description="Device type")
    fps_estimate: Optional[float] = Field(default=None, description="Estimated FPS")
    camera_resolution: Optional[str] = Field(
        default=None, description="Camera resolution (e.g., 1280x720)"
    )


class VerifyPuzzleRequest(BaseModel):
    """Request to verify puzzle completion."""

    puzzle_id: str = Field(..., description="Puzzle ID to verify")
    results: List[StepEvidence] = Field(
        ..., description="Evidence for each completed step"
    )
    final_frame: Optional[str] = Field(
        default=None, description="Base64 encoded final frame (for audit)"
    )
    client_meta: ClientMeta = Field(
        default_factory=ClientMeta, description="Client metadata"
    )


class VerifyPuzzleResponse(BaseModel):
    """Verification result."""

    success: bool = Field(..., description="Whether verification succeeded")
    liveness_confirmed: bool = Field(
        ..., description="Whether liveness is confirmed"
    )
    steps_completed: int = Field(..., description="Number of steps completed")
    total_steps: int = Field(..., description="Total number of steps")
    completion_time_seconds: float = Field(
        ..., description="Time taken to complete puzzle"
    )
    reason_codes: List[str] = Field(
        default_factory=list, description="Reason codes for failures"
    )
    overall_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall liveness score (0-100)"
    )
    message: str = Field(default="", description="Human-readable result message")


# Reason code constants for consistent error reporting
class ReasonCode:
    """Reason codes for puzzle verification failures."""

    PUZZLE_NOT_FOUND = "PUZZLE_NOT_FOUND"
    PUZZLE_EXPIRED = "PUZZLE_EXPIRED"
    PUZZLE_ALREADY_COMPLETED = "PUZZLE_ALREADY_COMPLETED"
    STEP_COUNT_MISMATCH = "STEP_COUNT_MISMATCH"
    STEP_ACTION_MISMATCH = "STEP_ACTION_MISMATCH"
    STEP_LOW_CONFIDENCE = "STEP_LOW_CONFIDENCE"
    TIMESTAMP_NOT_MONOTONIC = "TIMESTAMP_NOT_MONOTONIC"
    TIMESTAMP_BEFORE_PUZZLE = "TIMESTAMP_BEFORE_PUZZLE"
    STEP_TOO_SHORT = "STEP_TOO_SHORT"
    TIMESTAMPS_OVERLAP = "TIMESTAMPS_OVERLAP"
