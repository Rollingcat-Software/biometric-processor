"""Server-side re-scoring of puzzle-session landmark traces (contract v2).

Contract v1 (``score_action_metrics`` only) accepted ONE client-computed scalar
per challenge (``ear``, ``mar``, ``yaw`` …). A modified client could simply send
a passing number. Contract v2 (flag ``PUZZLE_TRACE_V2_ENABLED``) makes the
client submit a compact, timestamped **landmark trace** instead, and THIS module
recomputes everything from it:

  * the per-frame metric (EAR / MAR / brow ratio / head yaw+pitch for face;
    finger count / wrist motion / palm normal / fingertip distance for hand),
    with formulas ported 1:1 from the web engine (``FaceMetricsCalculator.ts``,
    ``handChallenges.ts``) or reused from :mod:`active_gesture_liveness_manager`;
  * the required **temporal shape** per action (blink = open→closed→open,
    head turn = rest→sustained excursion→return, mouth/brow = rest→sustained
    gesture, nod/shake = ≥2 direction reversals, tap = open→touch→release, …);
  * **per-step duration** floors and a global ceiling;
  * **timestamp sanity** (strictly increasing, plausible inter-frame interval);
  * basic **anti-synthesis plausibility** (natural landmark jitter present, no
    repeated/static frames, bounded inter-frame velocity and scale change).

The pass/fail THRESHOLDS stay single-sourced in
:func:`challenge_metric_scorer.score_action_metrics`: after the shape checks
pass, the trace-derived aggregate (e.g. the minimum EAR of the closed phase)
is fed through that same function.

What this does NOT prove (see docs/…/server_verification_v2 and the bio
CLAUDE.md puzzle section): a trace is still client-supplied data. These checks
make forging require synthesising a temporally coherent, jittered, physically
plausible landmark time-series rather than one number; they cannot prove the
landmarks came from a camera (camera-injection / synthetic-trace attackers are
out of scope).

Wire encoding (compact, see :data:`TRACE_COORD_SCALE`): each landmark
coordinate is sent as an integer in units of 1e-4 of the normalised MediaPipe
coordinate. A face frame carries the 32 landmarks in :data:`FACE_TRACE_INDICES`
order as a flat ``[x0,y0,z0,x1,y1,z1,…]`` list (96 ints); a hand frame carries
the 21 MediaPipe hand landmarks the same way (63 ints) or ``null`` when no hand
was visible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from app.api.schemas.active_liveness import ChallengeType
from app.application.services.challenge_metric_scorer import (
    _BROW_RAISE_MIN,
    _EYE_CLOSE_EAR_MAX,
    _HEAD_PITCH_MIN_DEG,
    _HEAD_YAW_MIN_DEG,
    _OPEN_MOUTH_MAR_MIN,
    _OSCILLATION_MIN,
    _SMILE_MAR_MIN,
    score_action_metrics,
)

# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------

TRACE_CONTRACT_VERSION = 2

#: Integer coordinate unit: value_on_wire = round(normalised_coord / 1e-4).
TRACE_COORD_SCALE: float = 1e-4

#: Hard bound on an encoded coordinate (|normalised| <= 2, as the gesture schema).
TRACE_COORD_ABS_MAX: int = 20_000

#: The 478-mesh indices a face frame carries, in wire order. Union of the
#: landmarks the web engine reads for EAR (both eyes), MAR + smile (lips +
#: corners), brow raise (both brows) and head pose / face scale (nose tip,
#: chin, forehead, nose bridge, cheek contours). Sorted ascending.
FACE_TRACE_INDICES: Tuple[int, ...] = (
    1, 10, 13, 14, 33, 61, 63, 66, 70, 105, 107, 133, 144, 152, 153, 158,
    160, 168, 234, 263, 291, 293, 296, 300, 334, 336, 362, 373, 380, 385,
    387, 454,
)
FACE_TRACE_POINTS = len(FACE_TRACE_INDICES)  # 32
HAND_TRACE_POINTS = 21

_POS = {idx: pos for pos, idx in enumerate(FACE_TRACE_INDICES)}

# Web engine index sets (web src/lib/biometric-engine/core/constants.ts).
_LEFT_EYE = (362, 385, 387, 263, 373, 380)
_RIGHT_EYE = (33, 160, 158, 133, 153, 144)
_UPPER_LIP, _LOWER_LIP, _MOUTH_LEFT, _MOUTH_RIGHT = 13, 14, 61, 291
_LEFT_EYEBROW = (70, 63, 105, 66, 107)
_RIGHT_EYEBROW = (300, 293, 334, 296, 336)
_EYE_OUTER_R, _EYE_OUTER_L = 33, 263  # inter-ocular scale reference

# Rigid (expression-insensitive) points for head-pose estimation and their
# MediaPipe canonical-face-model coordinates (cm; +X subject's left, +Y up,
# +Z toward the viewer). Source: mediapipe/modules/face_geometry/data/
# canonical_face_model.obj (Apache-2.0).
_POSE_CANONICAL: Dict[int, Tuple[float, float, float]] = {
    1: (0.0, -1.126865, 7.475604),
    10: (0.0, 8.261778, 4.481535),
    33: (-4.445859, 2.663991, 3.173422),
    133: (-1.856432, 2.585245, 3.757904),
    152: (0.0, -9.403378, 4.264492),
    168: (0.0, 3.271027, 5.236015),
    234: (-7.664182, 0.673132, -2.435867),
    263: (4.445859, 2.663991, 3.173422),
    362: (1.856432, 2.585245, 3.757904),
    454: (7.664182, 0.673132, -2.435867),
}
_POSE_IDX = tuple(_POSE_CANONICAL.keys())
_POSE_CANON = np.asarray([_POSE_CANONICAL[i] for i in _POSE_IDX], dtype=np.float64)

# Scale-normalised ratios used for the binding-frame consistency check
# (numerator pairs, all divided by the inter-ocular distance 33↔263).
_GEOMETRY_PAIRS: Tuple[Tuple[int, int], ...] = (
    (1, 152),    # nose tip → chin
    (168, 1),    # nose length
    (10, 152),   # face height
    (234, 454),  # face width (cheek contour)
    (33, 133),   # right eye width
    (362, 263),  # left eye width
    (10, 168),   # forehead → nose bridge
)

# ---------------------------------------------------------------------------
# Limits (all documented in the bio CLAUDE.md puzzle section)
# ---------------------------------------------------------------------------

MAX_TRACE_FRAMES = 200
MIN_FACE_FRAMES = 6
MIN_HAND_FRAMES = 5
#: Global ceiling on one challenge's trace span (client keeps ≤ ~4 s before
#: completion + ≤ 2 s return tail).
MAX_TRACE_SPAN_MS = 10_000.0
#: Minimum inter-frame interval (≈ 66 fps) — faster is not a real camera loop.
MIN_FRAME_INTERVAL_MS = 15.0
#: Maximum inter-frame gap (face/hand tracking may drop a few frames).
MAX_FRAME_GAP_MS = 700.0
#: Minimum frame size accepted for the isotropic (pixel) geometry.
_MIN_FRAME_DIM, _MAX_FRAME_DIM = 64, 8192

#: Per-action minimum trace span (ms). Mirrors the web gate timings
#: (HAND_HOLD_MS = 700, peek-a-boo cover ≥ 600 + reveal ≥ 350, …).
MIN_SPAN_MS: Dict[ChallengeType, float] = {
    ChallengeType.BLINK: 250.0,
    ChallengeType.CLOSE_LEFT_EYE: 300.0,
    ChallengeType.CLOSE_RIGHT_EYE: 300.0,
    ChallengeType.SMILE: 400.0,
    ChallengeType.OPEN_MOUTH: 400.0,
    ChallengeType.RAISE_EYEBROWS: 400.0,
    ChallengeType.RAISE_LEFT_BROW: 400.0,
    ChallengeType.RAISE_RIGHT_BROW: 400.0,
    ChallengeType.TURN_LEFT: 500.0,
    ChallengeType.TURN_RIGHT: 500.0,
    ChallengeType.LOOK_UP: 500.0,
    ChallengeType.LOOK_DOWN: 500.0,
    ChallengeType.NOD: 800.0,
    ChallengeType.SHAKE_HEAD: 800.0,
    ChallengeType.FINGER_COUNT: 500.0,
    ChallengeType.MATH: 500.0,
    ChallengeType.WAVE: 600.0,
    ChallengeType.HAND_FLIP: 400.0,
    ChallengeType.FINGER_TAP: 200.0,
    ChallengeType.PINCH: 700.0,
    ChallengeType.PEEK_A_BOO: 950.0,
    ChallengeType.HOLD_POSITION: 500.0,
    ChallengeType.SHAPE_TRACE: 800.0,
}

# Anti-synthesis plausibility bounds.
#: Median per-frame mean |second difference| of the normalised coordinates.
#: Real MediaPipe output on a live face carries ≳1e-4 of frame-to-frame noise;
#: a smooth (interpolated / spline) synthetic trace quantises to ~0.
MIN_NATURAL_JITTER = 5e-5
#: Max fraction of consecutive frame pairs that are bit-identical.
MAX_IDENTICAL_PAIR_FRACTION = 0.10
#: Max landmark speed, in face scales (inter-ocular distances) per second.
MAX_FACE_SPEED_SCALES_PER_S = 15.0
#: Max hand landmark speed, in hand scales (wrist→middle-MCP) per second.
MAX_HAND_SPEED_SCALES_PER_S = 60.0
#: Max per-frame |ln(scale_t / scale_{t-1})| (no teleporting toward the camera).
MAX_FACE_LOG_SCALE_STEP = 0.30
MAX_HAND_LOG_SCALE_STEP = 0.50

# Shape constants.
#: Head pose must come back within this fraction of the threshold ("return").
POSE_RETURN_FRACTION = 0.5
#: Eye must re-open at least this much above the closed threshold.
EYE_REOPEN_MARGIN = 0.03
#: Frames at the start of a trace used as the neutral baseline.
BASELINE_FRAMES = 3
#: Web OscillationCounter.OSCILLATION_MIN_SWING_DEG.
OSCILLATION_MIN_SWING_DEG = 8.0

# Hand constants ported from web handChallenges.ts.
TAP_TOUCH_THRESHOLD = 0.35
TAP_RELEASE_THRESHOLD = 0.60
TAP_MIN_TOUCH_FRAMES = 1  # at ≤25 fps sampling a 2-frame (30 fps) touch may be 1 frame
TAP_MAX_TOUCH_FRAMES = 20
PINCH_THRESHOLD = 0.35
HAND_HOLD_MS = 700.0
PEEK_COVER_MIN_MS = 600.0
PEEK_REVEAL_MIN_MS = 350.0

# Split-capture binding geometry tolerance.
BINDING_MAX_POSITION_RMS = 0.12  # in inter-ocular distances
BINDING_MAX_RATIO_DEVIATION = 0.10  # relative, per geometry ratio

FACE_ACTIONS = frozenset(
    {
        ChallengeType.BLINK,
        ChallengeType.CLOSE_LEFT_EYE,
        ChallengeType.CLOSE_RIGHT_EYE,
        ChallengeType.SMILE,
        ChallengeType.OPEN_MOUTH,
        ChallengeType.RAISE_EYEBROWS,
        ChallengeType.RAISE_LEFT_BROW,
        ChallengeType.RAISE_RIGHT_BROW,
        ChallengeType.TURN_LEFT,
        ChallengeType.TURN_RIGHT,
        ChallengeType.LOOK_UP,
        ChallengeType.LOOK_DOWN,
        ChallengeType.NOD,
        ChallengeType.SHAKE_HEAD,
    }
)
HAND_ACTIONS = frozenset(
    {
        ChallengeType.FINGER_COUNT,
        ChallengeType.MATH,
        ChallengeType.WAVE,
        ChallengeType.HAND_FLIP,
        ChallengeType.FINGER_TAP,
        ChallengeType.PINCH,
        ChallengeType.PEEK_A_BOO,
        ChallengeType.HOLD_POSITION,
        ChallengeType.SHAPE_TRACE,
    }
)

#: Difficulty → number of consecutive frames a sustained gesture must hold.
HOLD_FRAMES_BY_DIFFICULTY: Dict[str, int] = {"easy": 1, "standard": 2, "hard": 3}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FaceWindow:
    """A verified face challenge window, kept for the binding-frame consistency check."""

    times: np.ndarray  # (n,) ms, strictly increasing
    norm: np.ndarray  # (n, 32, 3) normalised coords
    width: int
    height: int

    @property
    def start(self) -> float:
        return float(self.times[0])

    @property
    def end(self) -> float:
        return float(self.times[-1])


@dataclass
class TraceVerdict:
    ok: bool
    reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    span_ms: float = 0.0
    face_window: Optional[FaceWindow] = None


# ---------------------------------------------------------------------------
# Decoding + generic checks
# ---------------------------------------------------------------------------


@dataclass
class _Decoded:
    times: np.ndarray
    width: int
    height: int
    face: Optional[np.ndarray]  # (n, 32, 3) normalised, or None for hand traces
    hand: List[Optional[np.ndarray]]  # per frame (21, 3) normalised or None


def _decode_points(raw: Any, n_points: int) -> Optional[np.ndarray]:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != n_points * 3:
        raise ValueError("BAD_LANDMARK_LENGTH")
    arr = np.asarray(raw, dtype=np.float64)
    if not np.all(np.isfinite(arr)) or np.any(np.abs(arr) > TRACE_COORD_ABS_MAX):
        raise ValueError("BAD_LANDMARK_VALUE")
    if np.any(arr != np.round(arr)):
        raise ValueError("BAD_LANDMARK_VALUE")
    return arr.reshape(n_points, 3) * TRACE_COORD_SCALE


def _decode(trace: Mapping[str, Any], modality: str) -> _Decoded:
    if int(trace.get("version", 0)) != TRACE_CONTRACT_VERSION:
        raise ValueError("TRACE_VERSION_UNSUPPORTED")
    width = int(trace.get("frame_width", 0))
    height = int(trace.get("frame_height", 0))
    if not (_MIN_FRAME_DIM <= width <= _MAX_FRAME_DIM and _MIN_FRAME_DIM <= height <= _MAX_FRAME_DIM):
        raise ValueError("BAD_FRAME_SIZE")
    frames = trace.get("frames") or []
    if len(frames) > MAX_TRACE_FRAMES:
        raise ValueError("TRACE_TOO_MANY_FRAMES")
    times: List[float] = []
    faces: List[np.ndarray] = []
    hands: List[Optional[np.ndarray]] = []
    for fr in frames:
        t = fr.get("t")
        if t is None or not isinstance(t, (int, float)) or not math.isfinite(float(t)):
            raise ValueError("BAD_TIMESTAMP")
        times.append(float(t))
        if modality == "face":
            pts = _decode_points(fr.get("f"), FACE_TRACE_POINTS)
            if pts is None:
                raise ValueError("FACE_LANDMARKS_MISSING")
            faces.append(pts)
        else:
            if fr.get("f") is not None:
                raise ValueError("UNEXPECTED_FACE_LANDMARKS")
            hands.append(_decode_points(fr.get("h"), HAND_TRACE_POINTS))
    return _Decoded(
        times=np.asarray(times, dtype=np.float64),
        width=width,
        height=height,
        face=np.stack(faces) if faces else None,
        hand=hands,
    )


def _check_timestamps(times: np.ndarray, action: ChallengeType) -> Optional[str]:
    if times.size < 2:
        return "TRACE_TOO_SHORT"
    dt = np.diff(times)
    if np.any(dt <= 0):
        return "TIMESTAMPS_NOT_MONOTONIC"
    if np.any(dt < MIN_FRAME_INTERVAL_MS):
        return "FRAME_INTERVAL_IMPLAUSIBLE"
    if np.any(dt > MAX_FRAME_GAP_MS):
        return "FRAME_GAP_TOO_LARGE"
    span = float(times[-1] - times[0])
    if span > MAX_TRACE_SPAN_MS:
        return "DURATION_TOO_LONG"
    if span < MIN_SPAN_MS.get(action, 300.0):
        return "DURATION_TOO_SHORT"
    return None


def _iso(points_norm: np.ndarray, width: int, height: int) -> np.ndarray:
    """Normalised MediaPipe coords → isotropic pixel-ish units (x·W, y·H, z·W)."""
    scale = np.asarray([width, height, width], dtype=np.float64)
    return points_norm * scale


def _plausibility(
    norm: np.ndarray,
    times: np.ndarray,
    iso: np.ndarray,
    scale: np.ndarray,
    max_speed: float,
    max_log_step: float,
) -> Optional[str]:
    """Generic anti-synthesis checks over a (n, k, 3) landmark sequence."""
    n = norm.shape[0]
    flat = norm.reshape(n, -1)
    identical = np.all(np.diff(flat, axis=0) == 0, axis=1)
    if identical.size and float(identical.mean()) > MAX_IDENTICAL_PAIR_FRACTION:
        return "STATIC_FRAMES"
    if n >= 3:
        d2 = np.abs(flat[2:] - 2.0 * flat[1:-1] + flat[:-2])
        jitter = float(np.median(d2.mean(axis=1)))
        if jitter < MIN_NATURAL_JITTER:
            return "NO_NATURAL_JITTER"
    if np.any(scale <= 1e-6):
        return "DEGENERATE_GEOMETRY"
    dt_s = np.diff(times) / 1000.0
    disp = np.linalg.norm(np.diff(iso[:, :, :2], axis=0), axis=2).max(axis=1)
    mean_scale = 0.5 * (scale[1:] + scale[:-1])
    speed = disp / mean_scale / dt_s
    if np.any(speed > max_speed):
        return "VELOCITY_IMPLAUSIBLE"
    if np.any(np.abs(np.diff(np.log(scale))) > max_log_step):
        return "SCALE_JUMP_IMPLAUSIBLE"
    return None


# ---------------------------------------------------------------------------
# Face metrics (1:1 ports of web FaceMetricsCalculator / HeadPoseEstimator)
# ---------------------------------------------------------------------------


def _pts(norm: np.ndarray, idxs: Sequence[int]) -> np.ndarray:
    return norm[:, [_POS[i] for i in idxs], :]


def _ear(norm: np.ndarray, eye: Sequence[int]) -> np.ndarray:
    p = _pts(norm, eye)[:, :, :2]
    d = lambda a, b: np.linalg.norm(p[:, a] - p[:, b], axis=1)
    horizontal = d(0, 3)
    out = (d(1, 5) + d(2, 4)) / np.where(horizontal == 0, 1.0, 2.0 * horizontal)
    return np.where(horizontal == 0, 0.3, out)


def _mar(norm: np.ndarray) -> np.ndarray:
    p = norm[:, :, :2]
    horiz = np.linalg.norm(p[:, _POS[_MOUTH_RIGHT]] - p[:, _POS[_MOUTH_LEFT]], axis=1)
    vert = np.linalg.norm(p[:, _POS[_LOWER_LIP]] - p[:, _POS[_UPPER_LIP]], axis=1)
    return np.where(horiz == 0, 0.0, vert / np.where(horiz == 0, 1.0, horiz))


def _brow_dists(norm: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = norm[:, :, 1]
    avg = lambda idxs: y[:, [_POS[i] for i in idxs]].mean(axis=1)
    left = avg(_LEFT_EYE) - avg(_LEFT_EYEBROW)
    right = avg(_RIGHT_EYE) - avg(_RIGHT_EYEBROW)
    return left, right, (left + right) / 2.0


def _head_pose(iso: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Per-frame (yaw, pitch) in degrees from a rigid Kabsch fit.

    Fits the canonical-face-model rigid subset to the observed landmarks
    (observed frame: +X image right, +Y up, +Z toward the camera, i.e. the
    MediaPipe z sign flipped) and reads the face's forward axis. Sign
    convention matches the cross-repo agreement: yaw < 0 = turned to the
    USER's left, pitch < 0 = looking up.
    """
    obs = iso[:, [_POS[i] for i in _POSE_IDX], :].copy()
    obs[:, :, 1] *= -1.0
    obs[:, :, 2] *= -1.0
    canon = _POSE_CANON - _POSE_CANON.mean(axis=0)
    yaws = np.empty(obs.shape[0])
    pitches = np.empty(obs.shape[0])
    for k in range(obs.shape[0]):
        o = obs[k] - obs[k].mean(axis=0)
        h = canon.T @ o
        u, _s, vt = np.linalg.svd(h)
        d = np.sign(np.linalg.det(vt.T @ u.T)) or 1.0
        r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
        fwd = r[:, 2]
        yaws[k] = -math.degrees(math.atan2(fwd[0], fwd[2]))
        pitches[k] = -math.degrees(math.atan2(fwd[1], math.hypot(fwd[0], fwd[2])))
    return yaws, pitches


def _face_scale(iso: np.ndarray) -> np.ndarray:
    return np.linalg.norm(
        iso[:, _POS[_EYE_OUTER_L], :2] - iso[:, _POS[_EYE_OUTER_R], :2], axis=1
    )


def _baseline(series: np.ndarray) -> float:
    return float(np.median(series[: min(BASELINE_FRAMES, series.size)]))


def _longest_run(mask: np.ndarray) -> Tuple[int, int, int]:
    """(length, start, end_inclusive) of the longest run of True."""
    best = (0, -1, -1)
    run_start = -1
    for i, v in enumerate(mask):
        if v and run_start < 0:
            run_start = i
        if (not v or i == mask.size - 1) and run_start >= 0:
            end = i if v else i - 1
            length = end - run_start + 1
            if length > best[0]:
                best = (length, run_start, end)
            run_start = -1
    return best


def _count_reversals(series: np.ndarray, min_swing: float) -> int:
    """Port of web FacePuzzle ``OscillationCounter``."""
    count = 0
    last_extreme: Optional[float] = None
    direction = 0
    for v in series:
        if last_extreme is None:
            last_extreme = float(v)
            continue
        delta = float(v) - last_extreme
        if abs(delta) < min_swing:
            continue
        new_dir = 1 if delta > 0 else -1
        if direction != 0 and new_dir != direction:
            count += 1
        direction = new_dir
        last_extreme = float(v)
    return count


def _verify_face(
    action: ChallengeType, dec: _Decoded, params: Dict[str, Any], hold: int
) -> TraceVerdict:
    norm = dec.face
    assert norm is not None
    times = dec.times
    if norm.shape[0] < MIN_FACE_FRAMES:
        return TraceVerdict(False, "TRACE_TOO_SHORT")
    reason = _check_timestamps(times, action)
    if reason:
        return TraceVerdict(False, reason)
    iso = _iso(norm, dec.width, dec.height)
    scale = _face_scale(iso)
    if float(np.median(scale)) < 20.0:
        return TraceVerdict(False, "FACE_TOO_SMALL")
    reason = _plausibility(
        norm, times, iso, scale, MAX_FACE_SPEED_SCALES_PER_S, MAX_FACE_LOG_SCALE_STEP
    )
    if reason:
        return TraceVerdict(False, reason)

    metrics: Dict[str, Any] = {}
    window = FaceWindow(times=times, norm=norm, width=dec.width, height=dec.height)
    span = float(times[-1] - times[0])

    if action in (ChallengeType.BLINK, ChallengeType.CLOSE_LEFT_EYE, ChallengeType.CLOSE_RIGHT_EYE):
        ear_l = _ear(norm, _LEFT_EYE)
        ear_r = _ear(norm, _RIGHT_EYE)
        if action == ChallengeType.BLINK:
            target, other = (ear_l + ear_r) / 2.0, None
        elif action == ChallengeType.CLOSE_LEFT_EYE:
            # Web mirror mapping: userLeftEAR = MediaPipe RIGHT_EYE EAR.
            target, other = ear_r, ear_l
        else:
            target, other = ear_l, ear_r
        closed = target <= _EYE_CLOSE_EAR_MAX
        if not closed.any():
            return TraceVerdict(False, "EYE_NOT_CLOSED")
        first, last = int(np.argmax(closed)), int(closed.size - 1 - np.argmax(closed[::-1]))
        open_level = _EYE_CLOSE_EAR_MAX + EYE_REOPEN_MARGIN
        if first == 0 or not np.any(target[:first] >= open_level):
            return TraceVerdict(False, "NO_OPEN_TO_CLOSED_TRANSITION")
        if last == closed.size - 1 or not np.any(target[last + 1 :] >= open_level):
            return TraceVerdict(False, "EYE_NOT_REOPENED")
        if action != ChallengeType.BLINK:
            run_len, rs, re_ = _longest_run(closed)
            if run_len < hold:
                return TraceVerdict(False, "GESTURE_NOT_SUSTAINED")
            if other is not None and float(np.median(other[rs : re_ + 1])) <= _EYE_CLOSE_EAR_MAX:
                return TraceVerdict(False, "WRONG_EYE_OR_BOTH_CLOSED")
        metrics["ear"] = float(target.min())

    elif action in (ChallengeType.SMILE, ChallengeType.OPEN_MOUTH):
        mar = _mar(norm)
        thr = _SMILE_MAR_MIN if action == ChallengeType.SMILE else _OPEN_MOUTH_MAR_MIN
        if _baseline(mar) >= thr:
            return TraceVerdict(False, "NO_REST_TO_GESTURE_TRANSITION")
        run_len, rs, re_ = _longest_run(mar >= thr)
        if run_len < hold:
            return TraceVerdict(
                False, "GESTURE_NOT_SUSTAINED" if run_len else
                ("SMILE_NOT_DETECTED" if action == ChallengeType.SMILE else "MOUTH_NOT_OPEN"),
            )
        metrics["mar"] = float(mar[rs : re_ + 1].max())

    elif action in (
        ChallengeType.RAISE_EYEBROWS,
        ChallengeType.RAISE_LEFT_BROW,
        ChallengeType.RAISE_RIGHT_BROW,
    ):
        left, right, both = _brow_dists(norm)
        series = {
            ChallengeType.RAISE_EYEBROWS: both,
            ChallengeType.RAISE_LEFT_BROW: left,
            ChallengeType.RAISE_RIGHT_BROW: right,
        }[action]
        base = _baseline(series)
        if base <= 0:
            return TraceVerdict(False, "DEGENERATE_GEOMETRY")
        # v2 brow metric = fractional increase of the brow→eye distance over the
        # in-trace neutral baseline (the v1 web ratio ≈ 1.0 at rest made the
        # scorer's ≥ 0.08 gate trivially satisfiable).
        increase = series / base - 1.0
        run_len, rs, re_ = _longest_run(increase >= _BROW_RAISE_MIN)
        if run_len < hold:
            return TraceVerdict(False, "BROW_NOT_RAISED" if run_len == 0 else "GESTURE_NOT_SUSTAINED")
        metrics["brow_raise"] = float(increase[rs : re_ + 1].max())

    elif action in (
        ChallengeType.TURN_LEFT,
        ChallengeType.TURN_RIGHT,
        ChallengeType.LOOK_UP,
        ChallengeType.LOOK_DOWN,
    ):
        yaw, pitch = _head_pose(iso)
        is_yaw = action in (ChallengeType.TURN_LEFT, ChallengeType.TURN_RIGHT)
        series = yaw if is_yaw else pitch
        thr = _HEAD_YAW_MIN_DEG if is_yaw else _HEAD_PITCH_MIN_DEG
        sign = -1.0 if action in (ChallengeType.TURN_LEFT, ChallengeType.LOOK_UP) else 1.0
        rel = series - _baseline(series)
        beyond = sign * rel >= thr
        run_len, rs, re_ = _longest_run(beyond)
        if run_len == 0:
            return TraceVerdict(False, "INSUFFICIENT_HEAD_YAW" if is_yaw else "INSUFFICIENT_HEAD_PITCH")
        if run_len < hold:
            return TraceVerdict(False, "GESTURE_NOT_SUSTAINED")
        if not np.any(np.abs(rel[re_ + 1 :]) <= POSE_RETURN_FRACTION * thr):
            return TraceVerdict(False, "POSE_NOT_RETURNED")
        peak = float(rel[rs : re_ + 1].min() if sign < 0 else rel[rs : re_ + 1].max())
        metrics["yaw" if is_yaw else "pitch"] = peak

    elif action in (ChallengeType.NOD, ChallengeType.SHAKE_HEAD):
        yaw, pitch = _head_pose(iso)
        series = pitch if action == ChallengeType.NOD else yaw
        osc = _count_reversals(series, OSCILLATION_MIN_SWING_DEG)
        if osc < _OSCILLATION_MIN:
            return TraceVerdict(False, "INSUFFICIENT_OSCILLATION")
        metrics["oscillation_count"] = osc

    else:
        return TraceVerdict(False, "TRACE_UNSUPPORTED_ACTION")

    rejection = score_action_metrics(action, metrics, params)
    if rejection is not None:
        return TraceVerdict(False, rejection[0], metrics)
    return TraceVerdict(True, None, metrics, span_ms=span, face_window=window)


# ---------------------------------------------------------------------------
# Hand
# ---------------------------------------------------------------------------


def _hand_dist_ratio(h: np.ndarray, a: int, b: int) -> float:
    """Web ``dist(lms[a], lms[b]) / handScale(lms)`` on normalised (x, y)."""
    scale = float(np.linalg.norm(h[0, :2] - h[9, :2])) or 1e-4
    return float(np.linalg.norm(h[a, :2] - h[b, :2])) / scale


def _verify_hand(
    action: ChallengeType,
    dec: _Decoded,
    params: Dict[str, Any],
    hold: int,
    gesture_manager: Any,
) -> TraceVerdict:
    times = dec.times
    reason = _check_timestamps(times, action)
    if reason:
        return TraceVerdict(False, reason)
    present_idx = [i for i, h in enumerate(dec.hand) if h is not None]
    if len(present_idx) < MIN_HAND_FRAMES:
        return TraceVerdict(False, "TRACE_TOO_SHORT")
    present_norm = np.stack([dec.hand[i] for i in present_idx])
    present_t = times[present_idx]
    iso = _iso(present_norm, dec.width, dec.height)
    scale = np.linalg.norm(iso[:, 0, :2] - iso[:, 9, :2], axis=1)
    if float(np.median(scale)) < 10.0:
        return TraceVerdict(False, "HAND_TOO_SMALL")
    # Velocity/jitter are only meaningful across CONTIGUOUS present frames;
    # check each contiguous segment separately (peek-a-boo has a gap).
    segments: List[List[int]] = []
    for k, i in enumerate(present_idx):
        if k and i == present_idx[k - 1] + 1:
            segments[-1].append(k)
        else:
            segments.append([k])
    longest = max(segments, key=len)
    if len(longest) >= 3:
        sel = np.asarray(longest)
        reason = _plausibility(
            present_norm[sel], present_t[sel], iso[sel], scale[sel],
            MAX_HAND_SPEED_SCALES_PER_S, MAX_HAND_LOG_SCALE_STEP,
        )
        if reason:
            return TraceVerdict(False, reason)
    else:
        return TraceVerdict(False, "TRACE_TOO_SHORT")

    metrics: Dict[str, Any] = {}
    span = float(times[-1] - times[0])

    if action in getattr(gesture_manager, "REPLAYABLE_TRACE_TYPES", ()):
        from app.api.schemas.gesture_liveness import HandLandmark

        frames: List[Tuple[int, Optional[List[HandLandmark]]]] = []
        t0 = times[0]
        for t, h in zip(times, dec.hand):
            lms = None
            if h is not None:
                lms = [
                    HandLandmark.model_construct(x=float(p[0]), y=float(p[1]), z=float(p[2]))
                    for p in h
                ]
            frames.append((round(t - t0), lms))
        result = gesture_manager.evaluate_trace(action, frames, params)
        if not result.detected:
            return TraceVerdict(False, {
                ChallengeType.FINGER_COUNT: "FINGER_COUNT_MISMATCH",
                ChallengeType.MATH: "FINGER_COUNT_MISMATCH",
                ChallengeType.WAVE: "INSUFFICIENT_WAVE",
                ChallengeType.HAND_FLIP: "HAND_NOT_FLIPPED",
                ChallengeType.HOLD_POSITION: "HAND_NOT_STILL",
                ChallengeType.SHAPE_TRACE: "SHAPE_MISMATCH",
            }.get(action, "GESTURE_NOT_DETECTED"))
        details = result.details
        if action in (ChallengeType.FINGER_COUNT, ChallengeType.MATH):
            metrics["finger_count"] = int(details.get("observed", -1))
        elif action == ChallengeType.WAVE:
            metrics["reversals"] = int(details.get("reversals", 0))
        elif action == ChallengeType.HAND_FLIP:
            metrics["orientation_changes"] = max(0, len(details.get("sign_sequence", [])) - 1)
        elif action == ChallengeType.HOLD_POSITION:
            metrics["wrist_variance"] = float(details.get("variance", 1.0))
        elif action == ChallengeType.SHAPE_TRACE:
            metrics["dtw_cost"] = float(details.get("dtw_cost", 1.0))

    elif action == ChallengeType.FINGER_TAP:
        d = np.asarray([_hand_dist_ratio(dec.hand[i], 4, 8) for i in present_idx])
        tapped = False
        seen_open = False
        touching = 0
        touch_min = math.inf
        for v in d:
            if v >= TAP_RELEASE_THRESHOLD:
                if seen_open and TAP_MIN_TOUCH_FRAMES <= touching <= TAP_MAX_TOUCH_FRAMES:
                    tapped = True
                    break
                seen_open = True
                touching = 0
                touch_min = math.inf
            elif v < TAP_TOUCH_THRESHOLD:
                touching += 1
                touch_min = min(touch_min, float(v))
        if not tapped:
            return TraceVerdict(False, "TAP_NOT_DETECTED")
        metrics["tap_dist_scaled"] = touch_min

    elif action == ChallengeType.PINCH:
        d = np.asarray([_hand_dist_ratio(dec.hand[i], 4, 8) for i in present_idx])
        if d[: min(BASELINE_FRAMES, d.size)].max() < PINCH_THRESHOLD:
            return TraceVerdict(False, "NO_REST_TO_GESTURE_TRANSITION")
        pinching = d < PINCH_THRESHOLD
        run_len, rs, re_ = _longest_run(pinching)
        if run_len < max(hold, 2) or present_t[re_] - present_t[rs] < HAND_HOLD_MS * 0.8:
            return TraceVerdict(False, "PINCH_NOT_DETECTED" if run_len == 0 else "GESTURE_NOT_SUSTAINED")
        metrics["pinch_dist_scaled"] = float(d[rs : re_ + 1].min())

    elif action == ChallengeType.PEEK_A_BOO:
        covered_start: Optional[float] = None
        last_covered: Optional[float] = None
        revealed = False
        for t, h in zip(times, dec.hand):
            if h is not None:
                cx, cy = float(h[9, 0]), float(h[9, 1])
                if 0.3 < cx < 0.7 and 0.25 < cy < 0.75:
                    if covered_start is None:
                        covered_start = float(t)
                    last_covered = float(t)
                # A hand still visible outside the centre is not a reveal.
            elif covered_start is not None and last_covered is not None:
                if t - last_covered >= PEEK_REVEAL_MIN_MS and last_covered - covered_start >= PEEK_COVER_MIN_MS:
                    revealed = True
                    break
        if not revealed:
            return TraceVerdict(False, "PEEK_A_BOO_INCOMPLETE")
        metrics["covered_then_revealed"] = True

    else:
        return TraceVerdict(False, "TRACE_UNSUPPORTED_ACTION")

    rejection = score_action_metrics(action, metrics, params)
    if rejection is not None:
        return TraceVerdict(False, rejection[0], metrics)
    return TraceVerdict(True, None, metrics, span_ms=span)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_trace(
    action: ChallengeType,
    trace: Mapping[str, Any],
    params: Optional[Dict[str, Any]] = None,
    *,
    hold_frames: int = HOLD_FRAMES_BY_DIFFICULTY["standard"],
    gesture_manager: Any = None,
) -> TraceVerdict:
    """Recompute + verify one challenge from its landmark trace (contract v2).

    Returns a :class:`TraceVerdict`; ``ok`` is True only when decoding, the
    timestamp rules, the plausibility rules, the action's temporal shape AND
    the shared metric threshold all pass.
    """
    params = params or {}
    if action in FACE_ACTIONS:
        modality = "face"
    elif action in HAND_ACTIONS:
        modality = "hand"
    else:
        return TraceVerdict(False, "TRACE_UNSUPPORTED_ACTION")
    try:
        dec = _decode(trace, modality)
    except (ValueError, TypeError, AttributeError) as exc:
        code = str(exc) if str(exc).isupper() else "TRACE_MALFORMED"
        return TraceVerdict(False, code)
    hold = max(1, int(hold_frames))
    if modality == "face":
        return _verify_face(action, dec, params, hold)
    if gesture_manager is None:
        from app.application.services.active_gesture_liveness_manager import (
            ActiveGestureLivenessManager,
        )

        gesture_manager = ActiveGestureLivenessManager()
    return _verify_hand(action, dec, params, hold, gesture_manager)


def _geometry_ratios(iso_pts: np.ndarray) -> np.ndarray:
    """(k,) scale-normalised inter-landmark ratios for one (32, 3) iso frame."""
    iod = float(np.linalg.norm(iso_pts[_POS[_EYE_OUTER_L], :2] - iso_pts[_POS[_EYE_OUTER_R], :2]))
    if iod <= 1e-6:
        return np.full(len(_GEOMETRY_PAIRS), np.nan)
    return np.asarray(
        [
            float(np.linalg.norm(iso_pts[_POS[a], :2] - iso_pts[_POS[b], :2])) / iod
            for a, b in _GEOMETRY_PAIRS
        ]
    )


def verify_binding_frame(
    windows: Sequence[FaceWindow], binding: Optional[Mapping[str, Any]]
) -> Optional[str]:
    """Binding-frame consistency check against the session's face windows.

    The client declares the timestamp + landmarks of the frame its identity
    embedding was computed from. Passes (returns ``None``) only when that
    timestamp lies inside the window of a VERIFIED face challenge of the same
    session AND the frame's geometry agrees with the trace at that instant
    (position RMS ≤ :data:`BINDING_MAX_POSITION_RMS` inter-ocular distances,
    every scale-normalised ratio within :data:`BINDING_MAX_RATIO_DEVIATION`).

    Scope (honest): this only checks the client-DECLARED frame against the
    client's OWN trace. It does NOT tie the matched 512-d embedding to the live
    capture: a modified client can pass it (declare any in-window frame, then
    submit an embedding from elsewhere). Real binding needs server-observed
    image data or attested capture. It raises the bar only for an unmodified
    or lightly modified client.
    """
    if not binding:
        return "BINDING_FRAME_REQUIRED"
    try:
        t_b = float(binding.get("t"))  # type: ignore[arg-type]
        pts = _decode_points(binding.get("f"), FACE_TRACE_POINTS)
    except (ValueError, TypeError):
        return "BINDING_FRAME_MALFORMED"
    if pts is None or not math.isfinite(t_b):
        return "BINDING_FRAME_MALFORMED"
    for w in windows:
        if not (w.start <= t_b <= w.end):
            continue
        j = int(np.searchsorted(w.times, t_b))
        if j < w.times.size and w.times[j] == t_b:
            ref = w.norm[j]
        else:
            t0, t1 = w.times[j - 1], w.times[j]
            a = (t_b - t0) / (t1 - t0)
            ref = (1.0 - a) * w.norm[j - 1] + a * w.norm[j]
        b_iso = _iso(pts, w.width, w.height)
        r_iso = _iso(ref, w.width, w.height)
        iod = float(np.linalg.norm(r_iso[_POS[_EYE_OUTER_L], :2] - r_iso[_POS[_EYE_OUTER_R], :2]))
        if iod <= 1e-6:
            return "BINDING_GEOMETRY_MISMATCH"
        rms = float(np.sqrt(np.mean(np.sum((b_iso[:, :2] - r_iso[:, :2]) ** 2, axis=1)))) / iod
        rb, rr = _geometry_ratios(b_iso), _geometry_ratios(r_iso)
        if not np.all(np.isfinite(rb)):
            return "BINDING_GEOMETRY_MISMATCH"
        ratio_dev = float(np.max(np.abs(rb - rr) / np.maximum(rr, 1e-6)))
        if rms > BINDING_MAX_POSITION_RMS or ratio_dev > BINDING_MAX_RATIO_DEVIATION:
            return "BINDING_GEOMETRY_MISMATCH"
        return None
    return "BINDING_OUTSIDE_WINDOW"


__all__ = [
    "TRACE_CONTRACT_VERSION",
    "TRACE_COORD_SCALE",
    "FACE_TRACE_INDICES",
    "FACE_ACTIONS",
    "HAND_ACTIONS",
    "HOLD_FRAMES_BY_DIFFICULTY",
    "FaceWindow",
    "TraceVerdict",
    "verify_trace",
    "verify_binding_frame",
]
