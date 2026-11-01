"""Unit tests for the puzzle contract v2 server-side trace verifier.

Every rule in :mod:`app.application.services.puzzle_trace_verifier` gets a
genuine-passes case and a targeted rejection. Traces are generated from the
MediaPipe canonical face geometry / an articulated hand
(``puzzle_trace_factory``) so they have realistic geometry, timing and jitter.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from app.api.schemas.active_liveness import ChallengeType as C
from app.application.services import puzzle_trace_verifier as V
from tests.unit.application.services import puzzle_trace_factory as F


# ---------------------------------------------------------------------------
# Genuine traces pass (and the recomputed metric clears the shared scorer gate)
# ---------------------------------------------------------------------------

GENUINE_FACE = [
    (C.BLINK, F.blink_trace, "ear"),
    (C.CLOSE_LEFT_EYE, lambda: F.wink_trace("right"), "ear"),
    (C.CLOSE_RIGHT_EYE, lambda: F.wink_trace("left"), "ear"),
    (C.TURN_LEFT, lambda: F.turn_trace(-25), "yaw"),
    (C.TURN_RIGHT, lambda: F.turn_trace(25), "yaw"),
    (C.LOOK_UP, lambda: F.look_trace(-18), "pitch"),
    (C.LOOK_DOWN, lambda: F.look_trace(18), "pitch"),
    (C.OPEN_MOUTH, lambda: F.mouth_trace(1.0), "mar"),
    (C.SMILE, lambda: F.mouth_trace(0.8), "mar"),
    (C.RAISE_EYEBROWS, F.brow_trace, "brow_raise"),
    (C.SHAKE_HEAD, F.shake_trace, "oscillation_count"),
    (C.NOD, F.nod_trace, "oscillation_count"),
]


@pytest.mark.parametrize("action,make,key", GENUINE_FACE, ids=[a.value for a, _, _ in GENUINE_FACE])
def test_genuine_face_trace_passes(action, make, key) -> None:
    r = V.verify_trace(action, make())
    assert r.ok, r.reason
    assert key in r.metrics
    assert r.face_window is not None


GENUINE_HAND = [
    (C.FINGER_COUNT, lambda: F.finger_count_trace(3), {"target": 3}),
    (C.MATH, lambda: F.finger_count_trace(2), {"target": 2}),
    (C.WAVE, F.wave_trace, {}),
    (C.HAND_FLIP, F.flip_trace, {}),
    (C.FINGER_TAP, F.tap_trace, {}),
    (C.PINCH, F.pinch_trace, {}),
    (C.PEEK_A_BOO, F.peek_trace, {}),
    (C.HOLD_POSITION, F.hold_trace, {}),
]


@pytest.mark.parametrize("action,make,params", GENUINE_HAND, ids=[a.value for a, _, _ in GENUINE_HAND])
def test_genuine_hand_trace_passes(action, make, params) -> None:
    r = V.verify_trace(action, make(), params)
    assert r.ok, r.reason


def test_head_pose_estimator_recovers_rotation_and_sign_convention() -> None:
    # yaw<0 = user's left, pitch<0 = looking up (cross-repo convention).
    for yaw, pitch in [(0, 0), (-20, 0), (20, 0), (0, -15), (0, 15), (-30, 10)]:
        iso = V._iso(F.face_points(yaw=yaw, pitch=pitch)[None], F.W, F.H)
        y, p = V._head_pose(iso)
        assert y[0] == pytest.approx(yaw, abs=0.5)
        assert p[0] == pytest.approx(pitch, abs=0.5)


def test_metric_formulas_match_web_engine_on_canonical_face() -> None:
    pts = F.face_points()[None]
    # Like the web FaceMetricsCalculator, EAR/MAR are computed on NORMALISED
    # (x, y): on a 4:3 frame the canonical face's isotropic EAR 0.234 / MAR
    # 0.1115 read as 0.234·(W/H) and 0.1115·(W/H).
    aspect = F.W / F.H
    assert V._ear(pts, V._LEFT_EYE)[0] == pytest.approx(0.2342 * aspect, abs=0.005)
    assert V._ear(pts, V._RIGHT_EYE)[0] == pytest.approx(0.2342 * aspect, abs=0.005)
    assert V._mar(pts)[0] == pytest.approx(0.1115 * aspect, abs=0.005)


# ---------------------------------------------------------------------------
# Temporal shape
# ---------------------------------------------------------------------------


def test_static_face_with_forged_metrics_fails() -> None:
    # A still, live-looking face never closes its eyes: the client-claimed
    # scalar is irrelevant, the server recomputes EAR and finds no closure.
    still = F.face_trace([(0, {}), (1200, {})])
    r = V.verify_trace(C.BLINK, still)
    assert not r.ok and r.reason == "EYE_NOT_CLOSED"


def test_blink_without_reopen_rejected() -> None:
    t = F.face_trace([(0, {}), (500, {}), (580, {"close_left": 1, "close_right": 1}), (900, {"close_left": 1, "close_right": 1})])
    assert V.verify_trace(C.BLINK, t).reason == "EYE_NOT_REOPENED"


def test_blink_starting_closed_rejected() -> None:
    t = F.face_trace([(0, {"close_left": 1, "close_right": 1}), (300, {"close_left": 1, "close_right": 1}), (400, {}), (900, {})])
    assert V.verify_trace(C.BLINK, t).reason == "NO_OPEN_TO_CLOSED_TRANSITION"


def test_wink_with_both_eyes_closed_rejected() -> None:
    t = F.face_trace([(0, {}), (400, {}), (500, {"close_left": 1, "close_right": 1}), (800, {"close_left": 1, "close_right": 1}), (900, {}), (1200, {})])
    assert V.verify_trace(C.CLOSE_LEFT_EYE, t).reason == "WRONG_EYE_OR_BOTH_CLOSED"


def test_head_turn_without_return_rejected() -> None:
    assert V.verify_trace(C.TURN_LEFT, F.turn_trace(-25, ret=False)).reason == "POSE_NOT_RETURNED"


def test_head_turn_wrong_direction_rejected() -> None:
    assert V.verify_trace(C.TURN_LEFT, F.turn_trace(25)).reason == "INSUFFICIENT_HEAD_YAW"


def test_head_turn_too_small_rejected() -> None:
    assert V.verify_trace(C.TURN_RIGHT, F.turn_trace(8)).reason == "INSUFFICIENT_HEAD_YAW"


def test_mouth_open_from_first_frame_rejected() -> None:
    t = F.face_trace([(0, {"mouth": 1}), (1000, {"mouth": 1})])
    assert V.verify_trace(C.OPEN_MOUTH, t).reason == "NO_REST_TO_GESTURE_TRANSITION"


def test_mouth_below_shared_threshold_rejected() -> None:
    # MAR peaks below the scorer's open-mouth threshold (0.50).
    assert V.verify_trace(C.OPEN_MOUTH, F.mouth_trace(0.4)).reason in ("MOUTH_NOT_OPEN",)


def test_nod_single_swing_rejected() -> None:
    t = F.face_trace([(0, {}), (400, {"pitch": 15}), (1000, {"pitch": 15})])
    assert V.verify_trace(C.NOD, t).reason == "INSUFFICIENT_OSCILLATION"


def test_difficulty_hold_frames_enforced() -> None:
    # Head turn held for a single sampled frame: passes at easy, fails at hard.
    t = F.face_trace([(0, {}), (560, {}), (600, {"yaw": -25}), (640, {}), (1100, {})], fps=25)
    assert V.verify_trace(C.TURN_LEFT, t, hold_frames=1).ok
    assert V.verify_trace(C.TURN_LEFT, t, hold_frames=3).reason == "GESTURE_NOT_SUSTAINED"


def test_finger_count_wrong_target_rejected() -> None:
    r = V.verify_trace(C.FINGER_COUNT, F.finger_count_trace(3), {"target": 4})
    assert r.reason == "FINGER_COUNT_MISMATCH"


def test_finger_count_without_server_target_rejected() -> None:
    assert not V.verify_trace(C.FINGER_COUNT, F.finger_count_trace(3), {}).ok


def test_pinch_held_from_start_rejected() -> None:
    t = F.hand_trace([(0, {"pinch": 1.0}), (1200, {"pinch": 1.0})])
    assert V.verify_trace(C.PINCH, t).reason == "NO_REST_TO_GESTURE_TRANSITION"


def test_peek_without_reveal_rejected() -> None:
    t = F.hand_trace([(0, {"wy": 0.55}), (1200, {"wy": 0.55})])
    assert V.verify_trace(C.PEEK_A_BOO, t).reason == "PEEK_A_BOO_INCOMPLETE"


def test_unsupported_actions_fail_closed() -> None:
    assert V.verify_trace(C.LIGHT, F.blink_trace()).reason == "TRACE_UNSUPPORTED_ACTION"
    # shape_trace needs a server-issued template_key; none issued → fail.
    assert not V.verify_trace(C.SHAPE_TRACE, F.wave_trace(), {}).ok


# ---------------------------------------------------------------------------
# Duration + timestamps
# ---------------------------------------------------------------------------


def test_trace_too_short_rejected() -> None:
    t = F.face_trace([(0, {}), (260, {"mouth": 1})])
    assert V.verify_trace(C.OPEN_MOUTH, t).reason == "DURATION_TOO_SHORT"


def test_trace_too_long_rejected() -> None:
    t = F.face_trace([(0, {}), (5000, {"mouth": 1}), (11000, {"mouth": 1})], fps=18)
    assert len(t["frames"]) <= V.MAX_TRACE_FRAMES
    assert V.verify_trace(C.OPEN_MOUTH, t).reason == "DURATION_TOO_LONG"


def test_non_monotonic_timestamps_rejected() -> None:
    t = F.blink_trace()
    fr = t["frames"]
    fr[5]["t"], fr[6]["t"] = fr[6]["t"], fr[5]["t"]
    assert V.verify_trace(C.BLINK, t).reason == "TIMESTAMPS_NOT_MONOTONIC"


def test_implausible_frame_interval_rejected() -> None:
    t = F.blink_trace()
    t["frames"][6]["t"] = t["frames"][5]["t"] + 3
    assert V.verify_trace(C.BLINK, t).reason == "FRAME_INTERVAL_IMPLAUSIBLE"


def test_large_gap_rejected() -> None:
    t = F.blink_trace()
    for fr in t["frames"][10:]:
        fr["t"] += 2000
    assert V.verify_trace(C.BLINK, t).reason == "FRAME_GAP_TOO_LARGE"


def test_too_many_frames_rejected() -> None:
    t = F.face_trace([(0, {}), (8500, {})], fps=25)
    assert len(t["frames"]) > V.MAX_TRACE_FRAMES
    assert V.verify_trace(C.BLINK, t).reason == "TRACE_TOO_MANY_FRAMES"


# ---------------------------------------------------------------------------
# Anti-synthesis plausibility
# ---------------------------------------------------------------------------


def test_identical_frames_rejected() -> None:
    t = F.blink_trace()
    for k in range(1, len(t["frames"])):
        if k % 3:
            t["frames"][k]["f"] = list(t["frames"][k - 1]["f"])
    assert V.verify_trace(C.BLINK, t).reason == "STATIC_FRAMES"


def test_smooth_synthetic_trace_without_jitter_rejected() -> None:
    # A perfectly smooth, interpolated head turn (what a naive synthesiser
    # emits) has no frame-to-frame landmark noise.
    t = F.face_trace(
        [(0, {"yaw": 0}), (700, {"yaw": -25}), (1400, {"yaw": 0})], jitter_px=0.0
    )
    assert V.verify_trace(C.TURN_LEFT, t).reason == "NO_NATURAL_JITTER"


def test_teleporting_face_rejected() -> None:
    t = F.blink_trace()
    pts = np.asarray(t["frames"][8]["f"], dtype=float).reshape(32, 3)
    pts[:, 0] += 2500  # +0.25 of the frame width in one 40 ms step
    t["frames"][8]["f"] = [int(v) for v in pts.reshape(-1)]
    assert V.verify_trace(C.BLINK, t).reason == "VELOCITY_IMPLAUSIBLE"


def test_face_scale_jump_rejected() -> None:
    t = F.blink_trace()
    for k in (8,):
        pts = np.asarray(t["frames"][k]["f"], dtype=float).reshape(32, 3)
        c = pts.mean(axis=0)
        pts = c + (pts - c) * 1.6
        t["frames"][k]["f"] = [int(v) for v in pts.reshape(-1)]
    assert V.verify_trace(C.BLINK, t).reason in ("SCALE_JUMP_IMPLAUSIBLE", "VELOCITY_IMPLAUSIBLE")


def test_teleporting_hand_rejected() -> None:
    t = F.wave_trace()
    pts = np.asarray(t["frames"][10]["h"], dtype=float).reshape(21, 3)
    pts[:, 1] -= 4000
    t["frames"][10]["h"] = [int(v) for v in pts.reshape(-1)]
    assert V.verify_trace(C.WAVE, t).reason == "VELOCITY_IMPLAUSIBLE"


# ---------------------------------------------------------------------------
# Decoding / shape guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda t: t.update(version=1), "TRACE_VERSION_UNSUPPORTED"),
        (lambda t: t.update(frame_width=10), "BAD_FRAME_SIZE"),
        (lambda t: t["frames"][0].update(f=[1, 2, 3]), "BAD_LANDMARK_LENGTH"),
        (lambda t: t["frames"][0]["f"].__setitem__(0, 99_999), "BAD_LANDMARK_VALUE"),
        (lambda t: t["frames"][0].pop("f"), "FACE_LANDMARKS_MISSING"),
    ],
)
def test_malformed_trace_rejected(mutate, code) -> None:
    t = F.blink_trace()
    mutate(t)
    assert V.verify_trace(C.BLINK, t).reason == code


def test_face_landmarks_on_hand_challenge_rejected() -> None:
    assert V.verify_trace(C.WAVE, F.blink_trace()).reason == "UNEXPECTED_FACE_LANDMARKS"


# ---------------------------------------------------------------------------
# Split-capture binding frame
# ---------------------------------------------------------------------------


def _window_and_frame(k: int = 4):
    t = F.blink_trace()
    r = V.verify_trace(C.BLINK, t)
    assert r.ok and r.face_window is not None
    fr = t["frames"][k]
    return r.face_window, t, {"t": fr["t"], "f": list(fr["f"])}


def test_binding_frame_inside_window_and_consistent_passes() -> None:
    w, _t, b = _window_and_frame()
    assert V.verify_binding_frame([w], b) is None


def test_binding_frame_between_frames_interpolates() -> None:
    w, t, _b = _window_and_frame()
    a, c = t["frames"][3], t["frames"][4]
    mid = {"t": (a["t"] + c["t"]) // 2, "f": a["f"]}
    assert V.verify_binding_frame([w], mid) is None


def test_binding_frame_missing_rejected() -> None:
    w, _t, _b = _window_and_frame()
    assert V.verify_binding_frame([w], None) == "BINDING_FRAME_REQUIRED"


def test_binding_frame_outside_window_rejected() -> None:
    w, t, b = _window_and_frame()
    b["t"] = t["frames"][-1]["t"] + 500
    assert V.verify_binding_frame([w], b) == "BINDING_OUTSIDE_WINDOW"


def test_binding_frame_from_other_face_geometry_rejected() -> None:
    # Same instant, but the landmarks of a different face (photo captured
    # elsewhere): wider face, different nose/chin proportions, other position.
    w, _t, b = _window_and_frame()
    other = F.face_points(cx=260, cy=220, px_per_cm=17.0)
    other[:, 1] = 0.45 + (other[:, 1] - 0.45) * 1.15
    b["f"] = F.encode(other)
    assert V.verify_binding_frame([w], b) == "BINDING_GEOMETRY_MISMATCH"


def test_binding_frame_geometry_check_is_scale_invariant_but_position_bound() -> None:
    w, _t, b = _window_and_frame()
    pts = np.asarray(b["f"], dtype=float).reshape(32, 3)
    pts[:, 0] += 600  # shifted by ~0.06 of the frame (~0.3 IOD) — not the same frame
    b["f"] = [int(v) for v in pts.reshape(-1)]
    assert V.verify_binding_frame([w], b) == "BINDING_GEOMETRY_MISMATCH"


def test_binding_frame_malformed_rejected() -> None:
    w, _t, b = _window_and_frame()
    b["f"] = b["f"][:10]
    assert V.verify_binding_frame([w], b) == "BINDING_FRAME_MALFORMED"


# ---------------------------------------------------------------------------
# Payload size (reported in docs)
# ---------------------------------------------------------------------------


def test_payload_size_per_challenge_is_bounded() -> None:
    sizes = {
        "blink": F.payload_bytes(F.blink_trace()),
        "turn_left": F.payload_bytes(F.turn_trace(-25)),
        "nod": F.payload_bytes(F.nod_trace()),
        "finger_count": F.payload_bytes(F.finger_count_trace(3)),
        "wave": F.payload_bytes(F.wave_trace()),
    }
    print("v2 trace payload bytes @25fps:", sizes)
    # ≈ 0.5 KB per face frame (32 landmarks) and ≈ 0.3 KB per hand frame.
    assert sizes["blink"] < 20_000
    assert sizes["turn_left"] < 30_000
    assert max(sizes.values()) < 30_000
    # The worst case accepted by the schema (200 face frames) stays < 120 KB.
    worst = F.face_trace([(0, {}), (7960, {})], fps=25)
    assert len(worst["frames"]) == 200
    assert F.payload_bytes(worst) < 120_000


def test_verify_does_not_mutate_input() -> None:
    t = F.blink_trace()
    snapshot = copy.deepcopy(t)
    V.verify_trace(C.BLINK, t)
    assert t == snapshot
