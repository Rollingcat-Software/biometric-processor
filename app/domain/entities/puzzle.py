"""Liveness puzzle domain entity.

This module defines the Puzzle aggregate and related value objects
for the liveness puzzle challenge-response system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import uuid


class PuzzleDifficulty(Enum):
    """Puzzle difficulty levels."""

    EASY = "easy"  # 2-3 steps, 7s per step
    STANDARD = "standard"  # 3-4 steps, 5s per step
    HARD = "hard"  # 4-5 steps, 4s per step


@dataclass(frozen=True)
class PuzzleStep:
    """Immutable puzzle step value object.

    Attributes:
        action: Challenge type (blink, smile, turn_left, etc.)
        duration_seconds: Time allowed to complete this step
        order: Step order (0-indexed)
    """

    action: str
    duration_seconds: float
    order: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "action": self.action,
            "duration_seconds": self.duration_seconds,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PuzzleStep":
        """Create from dictionary."""
        return cls(
            action=data["action"],
            duration_seconds=data["duration_seconds"],
            order=data["order"],
        )


@dataclass
class Puzzle:
    """Liveness puzzle aggregate.

    This is the root aggregate for the puzzle bounded context.
    It encapsulates the puzzle state and enforces invariants.

    Attributes:
        puzzle_id: Unique identifier
        steps: Ordered tuple of puzzle steps
        difficulty: Puzzle difficulty level
        created_at: Creation timestamp
        expires_at: Expiration timestamp
        tenant_id: Optional tenant identifier for multi-tenancy
        user_id: Optional user identifier
        completed: Whether the puzzle has been completed
        completion_time: Time taken to complete (if completed)
    """

    puzzle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: Tuple[PuzzleStep, ...] = field(default_factory=tuple)
    difficulty: PuzzleDifficulty = PuzzleDifficulty.STANDARD
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    completed: bool = False
    completion_time: Optional[float] = None

    def __post_init__(self):
        """Set default expiration if not provided."""
        if self.expires_at is None:
            # Default: 5 minutes from creation
            object.__setattr__(
                self, "expires_at", self.created_at + timedelta(minutes=5)
            )

    def is_expired(self) -> bool:
        """Check if puzzle has expired.

        Returns:
            True if current time is past expiration
        """
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if puzzle is still valid for use.

        Returns:
            True if puzzle is not expired and not already completed
        """
        return not self.is_expired() and not self.completed

    def get_total_duration(self) -> float:
        """Get total duration of all steps.

        Returns:
            Sum of all step durations in seconds
        """
        return sum(step.duration_seconds for step in self.steps)

    def validate_steps(
        self, submitted: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """Validate submitted steps match puzzle definition.

        Args:
            submitted: List of submitted step results

        Returns:
            Tuple of (is_valid, list of reason codes)
        """
        reasons = []

        # Check step count
        if len(submitted) != len(self.steps):
            reasons.append(
                f"STEP_COUNT_MISMATCH:expected={len(self.steps)},got={len(submitted)}"
            )
            return False, reasons

        # Check each step matches expected action
        for i, (expected, actual) in enumerate(zip(self.steps, submitted)):
            actual_action = actual.get("action", "")
            if expected.action != actual_action:
                reasons.append(
                    f"STEP_{i}_ACTION_MISMATCH:expected={expected.action},got={actual_action}"
                )

        return len(reasons) == 0, reasons

    def mark_completed(self, completion_time: float) -> None:
        """Mark puzzle as completed.

        Args:
            completion_time: Time taken to complete in seconds
        """
        self.completed = True
        self.completion_time = completion_time

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON/Redis storage
        """
        return {
            "puzzle_id": self.puzzle_id,
            "steps": [step.to_dict() for step in self.steps],
            "difficulty": self.difficulty.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "completed": self.completed,
            "completion_time": self.completion_time,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Puzzle":
        """Create puzzle from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Puzzle instance
        """
        steps = tuple(PuzzleStep.from_dict(s) for s in data.get("steps", []))

        return cls(
            puzzle_id=data["puzzle_id"],
            steps=steps,
            difficulty=PuzzleDifficulty(data.get("difficulty", "standard")),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            tenant_id=data.get("tenant_id"),
            user_id=data.get("user_id"),
            completed=data.get("completed", False),
            completion_time=data.get("completion_time"),
        )


@dataclass
class VerificationResult:
    """Result of puzzle verification.

    Attributes:
        success: Whether verification succeeded
        liveness_confirmed: Whether liveness is confirmed
        steps_completed: Number of steps that passed
        total_steps: Total number of steps
        completion_time_seconds: Time taken to complete
        reason_codes: List of failure reason codes
        overall_score: Overall liveness score (0-100)
    """

    success: bool
    liveness_confirmed: bool
    steps_completed: int
    total_steps: int
    completion_time_seconds: float
    reason_codes: List[str] = field(default_factory=list)
    overall_score: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "liveness_confirmed": self.liveness_confirmed,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "completion_time_seconds": self.completion_time_seconds,
            "reason_codes": self.reason_codes,
            "overall_score": self.overall_score,
        }
