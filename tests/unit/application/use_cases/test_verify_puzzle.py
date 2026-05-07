"""Unit tests for VerifyPuzzleUseCase.

P0-#9 regression (anti-replay spot-check defeated by corrupt frames):
``VerifyPuzzleUseCase._run_spot_check`` previously incremented
``failed_count`` only on ``is_live=False`` outcomes. Decode errors
(``cv2.imdecode`` returning ``None``) and detector exceptions hit a
``continue`` and were silently ignored. A client could therefore submit
3 corrupt JPEGs as ``spot_frames`` — every iteration would short-circuit
to ``continue``, ``failed_count`` would stay at 0, and the spot-check
would return ``True`` despite never actually verifying a single live
frame. This test pins the hardened contract: any frame we cannot
positively confirm as live is counted as a failure, and reaching the
threshold rejects the spot-check.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from app.application.use_cases.verify_puzzle import VerifyPuzzleUseCase
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.puzzle import Puzzle, PuzzleStep


def _make_puzzle() -> Puzzle:
    """Build a non-expired, not-completed puzzle with a single 'blink' step."""
    created_at = datetime.utcnow() - timedelta(seconds=2)
    return Puzzle(
        puzzle_id="puzzle-p0-9",
        steps=(PuzzleStep(action="blink", duration_seconds=1.0, order=0),),
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=5),
    )


def _valid_step_results(puzzle: Puzzle) -> list[dict]:
    """Build step results that, on their own, pass step/timestamp/confidence checks."""
    base = puzzle.created_at.timestamp() + 0.5
    return [
        {
            "action": "blink",
            "start_timestamp": base,
            "end_timestamp": base + 1.0,
            "confidence": 0.9,
        }
    ]


def _corrupt_frame_b64() -> str:
    """Return a base64-encoded blob that ``cv2.imdecode`` returns ``None`` for.

    JPEG magic bytes are FF D8 FF — random ASCII bytes are guaranteed to be
    rejected by the decoder.
    """
    return base64.b64encode(b"not-a-real-jpeg-frame").decode("ascii")


class _FakePuzzleRepository:
    """Minimal in-memory puzzle repository for unit tests."""

    def __init__(self, puzzle: Puzzle) -> None:
        self._puzzle = puzzle
        self.mark_completed = AsyncMock()

    async def get(self, puzzle_id: str) -> Puzzle | None:
        if puzzle_id == self._puzzle.puzzle_id:
            return self._puzzle
        return None

    async def save(self, puzzle: Puzzle) -> None:  # pragma: no cover
        self._puzzle = puzzle


@pytest.mark.asyncio
async def test_corrupt_frames_count_as_failures() -> None:
    """P0-#9: 3 corrupt JPEGs MUST cause spot-check rejection.

    Pre-fix behaviour: each corrupt frame hit ``continue`` and
    ``failed_count`` stayed at 0, so ``_run_spot_check`` returned
    ``(True, "")``. The use case then reported ``success=True`` and
    ``liveness_confirmed=True``, defeating the anti-replay control.

    Post-fix behaviour: each corrupt frame increments ``failed_count``,
    the threshold (>=2) is crossed, and the spot-check short-circuits to
    ``(False, "SPOT_CHECK_FAILED")``. The verification result MUST then
    surface ``SPOT_CHECK_FAILED`` and reject the puzzle.
    """
    puzzle = _make_puzzle()
    repository = _FakePuzzleRepository(puzzle)

    # Detector should never be reached for corrupt frames — but if the
    # implementation regressed and tried to call it with bad input, the
    # mock would raise (AsyncMock with side_effect) and that would still
    # be counted as a failure under the hardened contract.
    detector = Mock()
    detector.check_liveness = AsyncMock(
        side_effect=AssertionError(
            "detector must not be invoked for undecodable frames"
        )
    )

    use_case = VerifyPuzzleUseCase(
        puzzle_repository=repository,
        spot_check_detector=detector,
    )

    spot_frames = [_corrupt_frame_b64() for _ in range(3)]

    result = await use_case.execute(
        puzzle_id=puzzle.puzzle_id,
        results=_valid_step_results(puzzle),
        spot_frames=spot_frames,
    )

    assert result.success is False, (
        "3 corrupt spot-check frames must reject verification "
        "(P0-#9 anti-replay regression)"
    )
    assert result.liveness_confirmed is False
    assert "SPOT_CHECK_FAILED" in result.reason_codes
    repository.mark_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_detector_exception_counts_as_failure() -> None:
    """P0-#9: detector exceptions MUST count as spot-check failures.

    Under the pre-fix code, an exception inside the per-frame ``try``
    block hit ``continue`` and was lost. Now any exception increments
    ``failed_count``; two exceptions trip the threshold.
    """
    puzzle = _make_puzzle()
    repository = _FakePuzzleRepository(puzzle)

    detector = Mock()
    detector.check_liveness = AsyncMock(side_effect=RuntimeError("detector down"))

    use_case = VerifyPuzzleUseCase(
        puzzle_repository=repository,
        spot_check_detector=detector,
    )

    # Use real (decodable) frames so we exercise the detector path,
    # not the imdecode path.
    import cv2
    import numpy as np

    img = np.zeros((32, 32, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok, "test fixture: cv2.imencode failed"
    frame_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")

    spot_frames = [frame_b64, frame_b64, frame_b64]

    result = await use_case.execute(
        puzzle_id=puzzle.puzzle_id,
        results=_valid_step_results(puzzle),
        spot_frames=spot_frames,
    )

    assert result.success is False
    assert "SPOT_CHECK_FAILED" in result.reason_codes


@pytest.mark.asyncio
async def test_clean_live_frames_pass_spot_check() -> None:
    """Sanity: 3 frames with ``is_live=True`` must NOT trip the spot-check.

    Guards against an over-eager fix that would reject everything.
    """
    puzzle = _make_puzzle()
    repository = _FakePuzzleRepository(puzzle)

    detector = Mock()
    detector.check_liveness = AsyncMock(
        return_value=LivenessResult(
            is_live=True,
            score=92.0,
            challenge="passive",
            challenge_completed=True,
        )
    )

    use_case = VerifyPuzzleUseCase(
        puzzle_repository=repository,
        spot_check_detector=detector,
    )

    import cv2
    import numpy as np

    img = np.zeros((32, 32, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    frame_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")

    result = await use_case.execute(
        puzzle_id=puzzle.puzzle_id,
        results=_valid_step_results(puzzle),
        spot_frames=[frame_b64, frame_b64, frame_b64],
    )

    assert "SPOT_CHECK_FAILED" not in result.reason_codes
    assert result.success is True
    assert result.liveness_confirmed is True


@pytest.mark.asyncio
async def test_one_corrupt_frame_does_not_trip_threshold() -> None:
    """A single corrupt frame (below the >=2 threshold) must not reject.

    This locks the threshold semantics: ``MAX_FAILED_SPOT_CHECK_FRAMES``
    is the number that *trips* rejection, not the first bad frame.
    """
    puzzle = _make_puzzle()
    repository = _FakePuzzleRepository(puzzle)

    detector = Mock()
    detector.check_liveness = AsyncMock(
        return_value=LivenessResult(
            is_live=True,
            score=92.0,
            challenge="passive",
            challenge_completed=True,
        )
    )

    use_case = VerifyPuzzleUseCase(
        puzzle_repository=repository,
        spot_check_detector=detector,
    )

    import cv2
    import numpy as np

    img = np.zeros((32, 32, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    good_frame = base64.b64encode(encoded.tobytes()).decode("ascii")

    spot_frames = [_corrupt_frame_b64(), good_frame, good_frame]

    result = await use_case.execute(
        puzzle_id=puzzle.puzzle_id,
        results=_valid_step_results(puzzle),
        spot_frames=spot_frames,
    )

    assert "SPOT_CHECK_FAILED" not in result.reason_codes
    assert result.success is True
