"""Generate liveness puzzle use case.

This module provides the use case for generating randomized
liveness puzzles with configurable difficulty and step sequences.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple

from app.api.schemas.active_liveness import ChallengeType
from app.domain.entities.puzzle import Puzzle, PuzzleDifficulty, PuzzleStep
from app.domain.interfaces.puzzle_repository import IPuzzleRepository

logger = logging.getLogger(__name__)


class GeneratePuzzleUseCase:
    """Use case for generating liveness puzzles.

    This use case handles:
    - Random step generation based on difficulty
    - Avoiding incompatible step sequences
    - Persisting puzzle to repository with TTL
    - Returning puzzle with thresholds for client

    Following Single Responsibility Principle: Only handles puzzle generation.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    # Actions that shouldn't follow each other immediately
    # (physically uncomfortable or impossible to do quickly)
    INCOMPATIBLE_SEQUENCES: Set[Tuple[ChallengeType, ChallengeType]] = {
        (ChallengeType.TURN_LEFT, ChallengeType.TURN_RIGHT),
        (ChallengeType.TURN_RIGHT, ChallengeType.TURN_LEFT),
    }

    # Difficulty configuration
    DIFFICULTY_CONFIG = {
        PuzzleDifficulty.EASY: {
            "steps": (2, 3),
            "duration": 7.0,
        },
        PuzzleDifficulty.STANDARD: {
            "steps": (3, 4),
            "duration": 5.0,
        },
        PuzzleDifficulty.HARD: {
            "steps": (4, 5),
            "duration": 4.0,
        },
    }

    # Detection thresholds (sent to client for client-side processing)
    DEFAULT_THRESHOLDS = {
        "ear_threshold": 0.21,  # Eye Aspect Ratio for blink
        "mar_threshold": 0.4,  # Mouth Aspect Ratio for smile
        "head_turn_threshold": 0.15,  # Head turn angle
        "mouth_open_threshold": 0.5,  # Mouth open wide
        "eyebrow_threshold": 0.08,  # Eyebrow raise
    }

    def __init__(self, puzzle_repository: IPuzzleRepository):
        """Initialize generate puzzle use case.

        Args:
            puzzle_repository: Repository for puzzle persistence
        """
        self._repository = puzzle_repository
        logger.info("GeneratePuzzleUseCase initialized")

    def _get_available_challenges(self) -> List[ChallengeType]:
        """Get list of available challenge types.

        Returns:
            List of challenge types that can be used
        """
        return list(ChallengeType)

    def _is_incompatible_sequence(
        self,
        steps: List[PuzzleStep],
        candidate: ChallengeType,
    ) -> bool:
        """Check if adding candidate would create incompatible sequence.

        Args:
            steps: Current list of steps
            candidate: Candidate challenge to add

        Returns:
            True if sequence would be incompatible
        """
        if not steps:
            return False

        last_action = ChallengeType(steps[-1].action)
        return (last_action, candidate) in self.INCOMPATIBLE_SEQUENCES

    def _generate_steps(
        self,
        difficulty: PuzzleDifficulty,
        min_steps: int,
        max_steps: int,
    ) -> List[PuzzleStep]:
        """Generate random puzzle steps.

        Args:
            difficulty: Difficulty level
            min_steps: Minimum number of steps
            max_steps: Maximum number of steps

        Returns:
            List of puzzle steps
        """
        config = self.DIFFICULTY_CONFIG[difficulty]

        # Determine number of steps
        config_min, config_max = config["steps"]
        num_steps = random.randint(
            max(min_steps, config_min),
            min(max_steps, config_max),
        )

        available = self._get_available_challenges()
        steps: List[PuzzleStep] = []

        for i in range(num_steps):
            # Filter out incompatible actions
            valid_candidates = [
                c for c in available
                if not self._is_incompatible_sequence(steps, c)
            ]

            # If all filtered out, use all (shouldn't happen with current rules)
            if not valid_candidates:
                valid_candidates = available

            # Avoid repeating the same action twice in a row
            if steps:
                last_action = steps[-1].action
                valid_candidates = [
                    c for c in valid_candidates
                    if c.value != last_action
                ] or valid_candidates

            # Select random action
            action = random.choice(valid_candidates)

            steps.append(
                PuzzleStep(
                    action=action.value,
                    duration_seconds=config["duration"],
                    order=i,
                )
            )

        return steps

    async def execute(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        difficulty: str = "standard",
        min_steps: int = 3,
        max_steps: int = 4,
        timeout_seconds: int = 60,
    ) -> Puzzle:
        """Execute puzzle generation.

        Args:
            tenant_id: Optional tenant identifier
            user_id: Optional user identifier
            difficulty: Difficulty level (easy, standard, hard)
            min_steps: Minimum number of steps
            max_steps: Maximum number of steps
            timeout_seconds: Total puzzle timeout

        Returns:
            Generated puzzle entity

        Raises:
            ValueError: If difficulty is invalid
        """
        logger.info(
            f"Generating puzzle: difficulty={difficulty}, "
            f"steps={min_steps}-{max_steps}, timeout={timeout_seconds}s"
        )

        # Parse difficulty
        try:
            diff = PuzzleDifficulty(difficulty)
        except ValueError:
            raise ValueError(
                f"Invalid difficulty: {difficulty}. "
                f"Must be one of: easy, standard, hard"
            )

        # Generate steps
        steps = self._generate_steps(diff, min_steps, max_steps)

        # Create puzzle entity
        puzzle = Puzzle(
            steps=tuple(steps),
            difficulty=diff,
            expires_at=datetime.utcnow() + timedelta(seconds=timeout_seconds + 60),
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # Persist puzzle
        await self._repository.save(puzzle)

        logger.info(
            f"Generated puzzle {puzzle.puzzle_id}: "
            f"{len(steps)} steps, expires={puzzle.expires_at.isoformat()}"
        )

        return puzzle

    def get_thresholds(self) -> dict:
        """Get detection thresholds for client.

        Returns:
            Dictionary of threshold values
        """
        return self.DEFAULT_THRESHOLDS.copy()
