"""Cross-repo puzzle contract: a web-client completion must be server-accepted.

``tests/fixtures/puzzle_contract/puzzle_contract_golden_traces.json.gz`` is
produced by the web-app vitest
``src/features/biometric-puzzles/__tests__/puzzleContract.test.ts``: it runs the
REAL web ``BiometricPuzzle`` engine + ``PuzzleTraceRecorder`` over real
MediaPipe landmark segments (stock face videos, one genuine gesture per face
challenge; derived landmarks only, no images) and records the v2 trace the
client would SUBMIT at each completion. The same file is committed in both
repos. Here we assert:

* every client-completed trace is ACCEPTED by the real ``verify_trace``
  (design rule: client "completed" implies server accept), and
* the thresholds the web client holds (recorded in the golden file from the web
  constants module) equal the server's own constants, so a change on one side
  fails a test on the other.

Regenerate on the web side (``UPDATE_PUZZLE_CONTRACT=1``) and copy the file here
after an intentional engine / recorder / threshold change.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.api.schemas.active_liveness import ChallengeType
from app.application.services import challenge_metric_scorer as S
from app.application.services import puzzle_trace_verifier as V

_GOLDEN = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "puzzle_contract"
    / "puzzle_contract_golden_traces.json.gz"
)


def _load() -> dict:
    with gzip.open(_GOLDEN, "rt", encoding="utf-8") as fh:
        return json.load(fh)


_DOC = _load()
_TRACES = _DOC["traces"]


def test_golden_covers_every_face_action() -> None:
    actions = {ChallengeType[t["server_action"]] for t in _TRACES}
    assert actions == {
        ChallengeType.BLINK,
        ChallengeType.CLOSE_LEFT_EYE,
        ChallengeType.CLOSE_RIGHT_EYE,
        ChallengeType.SMILE,
        ChallengeType.OPEN_MOUTH,
        ChallengeType.TURN_LEFT,
        ChallengeType.TURN_RIGHT,
        ChallengeType.LOOK_UP,
        ChallengeType.LOOK_DOWN,
        ChallengeType.RAISE_EYEBROWS,
        ChallengeType.RAISE_LEFT_BROW,
        ChallengeType.RAISE_RIGHT_BROW,
        ChallengeType.NOD,
        ChallengeType.SHAKE_HEAD,
    }
    assert len(_TRACES) == 14


@pytest.mark.parametrize("item", _TRACES, ids=[t["id"] for t in _TRACES])
def test_every_client_completion_is_server_accepted(item: dict) -> None:
    action = ChallengeType[item["server_action"]]
    verdict = V.verify_trace(action, item["trace"], {}, hold_frames=item["hold_frames"])
    assert verdict.ok, f"{item['id']}: client completed but server rejected: {verdict.reason}"


def test_client_thresholds_equal_server_constants() -> None:
    c = _DOC["constants"]
    assert c["blink_reopen_ear"] == pytest.approx(S._EYE_CLOSE_EAR_MAX + V.EYE_REOPEN_MARGIN)
    assert c["open_mouth_mar_min"] == S._OPEN_MOUTH_MAR_MIN
    assert c["smile_corner_raise_min"] == S._SMILE_CORNER_RAISE_MIN
    assert c["smile_corner_abs_min"] == S._SMILE_CORNER_ABS_MIN
    assert c["smile_width_ratio_min"] == S._SMILE_WIDTH_RATIO_MIN
    assert c["brow_raise_both_min"] == S._BROW_RAISE_V2_BOTH_MIN
    assert c["brow_raise_single_min"] == S._BROW_RAISE_V2_SINGLE_MIN
    assert c["oscillation_min_swing_deg"] == V.OSCILLATION_MIN_SWING_DEG
    assert c["oscillation_min_reversals"] == S._OSCILLATION_MIN
    assert c["pose_baseline_frames"] == V.BASELINE_FRAMES
    assert c["expression_baseline_frames"] == V.EXPRESSION_BASELINE_FRAMES
    assert c["tap_max_dist_scaled"] == S._FINGER_TAP_MAX_DIST_SCALED
    assert c["pinch_max_dist_scaled"] == S._PINCH_MAX_DIST_SCALED


def test_client_baseline_is_the_trace_start() -> None:
    """The client's attempt baseline (oldest samples of its rolling window) is
    the server's baseline (first trace frames) only when both windows and both
    sampling intervals are the same."""
    c = _DOC["constants"]
    assert c["attempt_window_ms"] == c["trace_window_ms"]
    assert c["attempt_sample_interval_ms"] == c["trace_min_interval_ms"]
    assert c["trace_min_interval_ms"] >= V.MIN_FRAME_INTERVAL_MS
