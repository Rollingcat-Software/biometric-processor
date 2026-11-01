"""Programmatic, physically realistic landmark traces for puzzle contract v2 tests.

Face frames are produced by deforming + rotating the MediaPipe canonical face
model (the same 3D geometry MediaPipe's own face-geometry pipeline fits), then
orthographically projecting it into a 640x480 camera frame in MediaPipe's
normalised (x, y, z) convention and adding per-landmark Gaussian jitter of the
order MediaPipe exhibits on a live face (~0.5 px). Hand frames are built from a
simple articulated 21-point hand. Everything is encoded exactly as the web
client sends it (ints in 1e-4 units).
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from app.application.services.puzzle_trace_verifier import (
    FACE_TRACE_INDICES,
    TRACE_COORD_SCALE,
)

W, H = 640, 480

# MediaPipe canonical_face_model.obj vertices for the 32 trace indices (cm).
CANONICAL: Dict[int, Tuple[float, float, float]] = {
    1: (0.0, -1.126865, 7.475604),
    10: (0.0, 8.261778, 4.481535),
    13: (0.0, -3.994436, 5.219482),
    14: (0.0, -4.5424, 5.404754),
    33: (-4.445859, 2.663991, 3.173422),
    61: (-2.456206, -4.342621, 4.283884),
    63: (-4.985894, 4.802461, 3.751977),
    66: (-2.760292, 5.100971, 5.01599),
    70: (-5.720968, 4.254584, 2.830852),
    105: (-3.986562, 5.109487, 4.466315),
    107: (-1.395634, 5.011963, 5.316032),
    133: (-1.856432, 2.585245, 3.757904),
    144: (-3.670075, 2.360153, 3.63523),
    152: (0.0, -9.403378, 4.264492),
    153: (-2.724032, 2.315802, 3.777151),
    158: (-2.724032, 2.96181, 3.871767),
    160: (-3.670075, 2.927714, 3.724325),
    168: (0.0, 3.271027, 5.236015),
    234: (-7.664182, 0.673132, -2.435867),
    263: (4.445859, 2.663991, 3.173422),
    291: (2.456206, -4.342621, 4.283884),
    293: (4.985894, 4.802461, 3.751977),
    296: (2.760292, 5.100971, 5.01599),
    300: (5.720968, 4.254584, 2.830852),
    334: (3.986562, 5.109487, 4.466315),
    336: (1.395634, 5.011963, 5.316032),
    362: (1.856432, 2.585245, 3.757904),
    373: (3.670075, 2.360153, 3.63523),
    380: (2.724032, 2.315802, 3.777151),
    385: (2.724032, 2.96181, 3.871767),
    387: (3.670075, 2.927714, 3.724325),
    454: (7.664182, 0.673132, -2.435867),
}
_BASE = np.asarray([CANONICAL[i] for i in FACE_TRACE_INDICES], dtype=np.float64)
_P = {idx: k for k, idx in enumerate(FACE_TRACE_INDICES)}
# Upper-lid → lower-lid pairs, per MediaPipe eye (LEFT_EYE = 362.., RIGHT_EYE = 33..).
_LIDS_LEFT = ((385, 380), (387, 373))
_LIDS_RIGHT = ((160, 144), (158, 153))
_BROWS = (70, 63, 105, 66, 107, 300, 293, 334, 296, 336)
_BROWS_L = (70, 63, 105, 66, 107)
_BROWS_R = (300, 293, 334, 296, 336)


def face_points(
    *,
    yaw: float = 0.0,
    pitch: float = 0.0,
    close_left: float = 0.0,
    close_right: float = 0.0,
    mouth: float = 0.0,
    brow: float = 0.0,
    brow_l: float = 0.0,
    brow_r: float = 0.0,
    cx: float = 320.0,
    cy: float = 240.0,
    px_per_cm: float = 14.0,
    jitter_px: float = 0.5,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """(32, 3) normalised MediaPipe-style landmarks for one face pose/expression.

    ``yaw``/``pitch`` follow the cross-repo convention (yaw<0 = user's left,
    pitch<0 = looking up). ``close_left``/``close_right`` close the MediaPipe
    LEFT_EYE (362..) / RIGHT_EYE (33..) lids (0 open .. 1 shut).
    """
    p = _BASE.copy()
    for amount, lids in ((close_left, _LIDS_LEFT), (close_right, _LIDS_RIGHT)):
        for up, lo in lids:
            p[_P[up], 1] = p[_P[up], 1] + amount * 0.95 * (p[_P[lo], 1] - p[_P[up], 1])
    p[_P[14], 1] -= mouth * 3.0
    for i in _BROWS:
        p[_P[i], 1] += brow * 0.6
    for i in _BROWS_L:
        p[_P[i], 1] += brow_l * 0.6
    for i in _BROWS_R:
        p[_P[i], 1] += brow_r * 0.6
    th = math.radians(-yaw)
    ph = math.radians(pitch)
    ry = np.asarray([[math.cos(th), 0, math.sin(th)], [0, 1, 0], [-math.sin(th), 0, math.cos(th)]])
    rx = np.asarray([[1, 0, 0], [0, math.cos(ph), -math.sin(ph)], [0, math.sin(ph), math.cos(ph)]])
    q = (ry @ rx @ p.T).T * px_per_cm
    out = np.empty_like(q)
    out[:, 0] = (cx + q[:, 0]) / W
    out[:, 1] = (cy - q[:, 1]) / H
    out[:, 2] = -q[:, 2] / W
    if rng is not None and jitter_px > 0:
        out[:, 0] += rng.normal(0, jitter_px / W, out.shape[0])
        out[:, 1] += rng.normal(0, jitter_px / H, out.shape[0])
        out[:, 2] += rng.normal(0, jitter_px / W, out.shape[0])
    return out


def encode(points: np.ndarray) -> List[int]:
    return [int(round(v / TRACE_COORD_SCALE)) for v in points.reshape(-1)]


def _interp(keys: Sequence[Tuple[float, Dict[str, float]]], t: float) -> Dict[str, float]:
    if t <= keys[0][0]:
        return dict(keys[0][1])
    for (t0, a), (t1, b) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            w = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            names = set(a) | set(b)
            return {k: (1 - w) * a.get(k, 0.0) + w * b.get(k, 0.0) for k in names}
    return dict(keys[-1][1])


def face_trace(
    keys: Sequence[Tuple[float, Dict[str, float]]],
    *,
    fps: float = 25.0,
    t0: float = 10_000.0,
    seed: int = 7,
    jitter_px: float = 0.5,
) -> Dict[str, Any]:
    """Keyframed face trace (keys = [(ms_from_start, face_points kwargs), ...])."""
    rng = np.random.default_rng(seed)
    dur = keys[-1][0]
    n = int(dur * fps / 1000.0) + 1
    frames = []
    for k in range(n):
        t = k * 1000.0 / fps
        pts = face_points(**_interp(keys, t), rng=rng, jitter_px=jitter_px)
        frames.append({"t": int(round(t0 + t)), "f": encode(pts)})
    return {"version": 2, "frame_width": W, "frame_height": H, "frames": frames}


# Canonical genuine face gestures --------------------------------------------

def blink_trace(**kw: Any) -> Dict[str, Any]:
    return face_trace(
        [(0, {}), (500, {}), (580, {"close_left": 1, "close_right": 1}),
         (700, {"close_left": 1, "close_right": 1}), (780, {}), (1100, {})], **kw
    )


def wink_trace(eye: str = "right", **kw: Any) -> Dict[str, Any]:
    key = "close_right" if eye == "right" else "close_left"
    return face_trace([(0, {}), (400, {}), (500, {key: 1}), (800, {key: 1}), (900, {}), (1200, {})], **kw)


def turn_trace(yaw: float = -25.0, *, ret: bool = True, **kw: Any) -> Dict[str, Any]:
    keys = [(0, {}), (300, {}), (800, {"yaw": yaw}), (1200, {"yaw": yaw})]
    if ret:
        keys += [(1700, {}), (1900, {})]
    return face_trace(keys, **kw)


def look_trace(pitch: float = -18.0, **kw: Any) -> Dict[str, Any]:
    return face_trace([(0, {}), (300, {}), (800, {"pitch": pitch}), (1200, {"pitch": pitch}), (1700, {}), (1900, {})], **kw)


def mouth_trace(level: float = 1.0, **kw: Any) -> Dict[str, Any]:
    return face_trace([(0, {}), (400, {}), (700, {"mouth": level}), (1200, {"mouth": level})], **kw)


def brow_trace(**kw: Any) -> Dict[str, Any]:
    return face_trace([(0, {}), (400, {}), (700, {"brow": 1}), (1200, {"brow": 1})], **kw)


def shake_trace(**kw: Any) -> Dict[str, Any]:
    return face_trace(
        [(0, {}), (300, {"yaw": -20}), (700, {"yaw": 20}), (1100, {"yaw": -20}), (1500, {"yaw": 20}), (1800, {})], **kw
    )


def nod_trace(**kw: Any) -> Dict[str, Any]:
    return face_trace(
        [(0, {}), (300, {"pitch": -15}), (700, {"pitch": 15}), (1100, {"pitch": -15}), (1500, {"pitch": 15}), (1800, {})], **kw
    )


# Hand ------------------------------------------------------------------------

def hand_points(
    *,
    open_fingers: Iterable[int] = (0, 1, 2, 3, 4),
    wx: float = 0.5,
    wy: float = 0.7,
    size: float = 0.12,
    flip: bool = False,
    pinch: float = 0.0,
    jitter: float = 0.0008,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """(21, 3) normalised hand landmarks, palm up, fingers pointing to -y.

    ``open_fingers`` = subset of 0..4 (thumb..pinky) extended; ``pinch`` in
    0..1 brings the thumb tip onto the index tip; ``flip`` mirrors the hand
    about the wrist's vertical axis (palm ↔ back).
    """
    opened = set(open_fingers)
    sx = -1.0 if flip else 1.0
    pts = np.zeros((21, 3))
    pts[0] = (0.0, 0.0, 0.0)
    bases = {1: -0.35, 2: -0.12, 3: 0.08, 4: 0.28}  # x offsets of MCPs (index..pinky)
    for f, bx in bases.items():
        mcp = 1 + 4 * f
        pts[mcp] = (bx, -0.95, 0.0)
        ext = f in opened
        for j in range(1, 4):
            if ext:
                pts[mcp + j] = (bx, -0.95 - 0.33 * j, -0.01 * j)
            else:  # curled back toward the palm
                pts[mcp + j] = (bx, -0.95 + 0.12 * j - (0.25 if j == 1 else 0.0), -0.08 * j)
    # Thumb: CMC, MCP, IP, TIP.
    if 0 in opened:
        thumb = [(-0.25, -0.2), (-0.55, -0.4), (-0.8, -0.55), (-1.05, -0.7)]
    else:
        thumb = [(-0.25, -0.2), (-0.35, -0.45), (-0.2, -0.6), (-0.05, -0.65)]
    for j, (x, y) in enumerate(thumb):
        pts[1 + j] = (x, y, -0.02 * j)
    if pinch > 0:
        tip = pts[8].copy()
        pts[4] = (1 - pinch) * pts[4] + pinch * tip
        pts[3] = (1 - pinch) * pts[3] + pinch * (tip + np.asarray([-0.15, 0.1, 0.0]))
    pts[:, 0] *= sx
    out = np.empty_like(pts)
    out[:, 0] = wx + pts[:, 0] * size
    out[:, 1] = wy + pts[:, 1] * size * (W / H)
    out[:, 2] = pts[:, 2] * size
    if rng is not None and jitter > 0:
        out += rng.normal(0, jitter, out.shape)
    return out


def hand_trace(
    keys: Sequence[Tuple[float, Optional[Dict[str, Any]]]],
    *,
    fps: float = 25.0,
    t0: float = 20_000.0,
    seed: int = 11,
) -> Dict[str, Any]:
    """Keyframed hand trace; a key value of ``None`` = no hand visible."""
    rng = np.random.default_rng(seed)
    dur = keys[-1][0]
    n = int(dur * fps / 1000.0) + 1
    frames = []
    for k in range(n):
        t = k * 1000.0 / fps
        # step-wise for discrete params, linear for numeric wx/wy/pinch
        prev = keys[0]
        nxt = keys[-1]
        for a, b in zip(keys, keys[1:]):
            if a[0] <= t <= b[0]:
                prev, nxt = a, b
                break
        if prev[1] is None:
            frames.append({"t": int(round(t0 + t)), "h": None})
            continue
        kw = dict(prev[1])
        if nxt[1] is not None and nxt[0] > prev[0]:
            w = (t - prev[0]) / (nxt[0] - prev[0])
            for name in ("wx", "wy", "pinch"):
                if name in prev[1] or name in nxt[1]:
                    a = prev[1].get(name, {"wx": 0.5, "wy": 0.7, "pinch": 0.0}[name])
                    b = nxt[1].get(name, {"wx": 0.5, "wy": 0.7, "pinch": 0.0}[name])
                    kw[name] = (1 - w) * a + w * b
        frames.append({"t": int(round(t0 + t)), "h": encode(hand_points(rng=rng, **kw))})
    return {"version": 2, "frame_width": W, "frame_height": H, "frames": frames}


def payload_bytes(trace: Dict[str, Any]) -> int:
    """Compact JSON size of a trace as the browser would send it."""
    return len(json.dumps(trace, separators=(",", ":")).encode())


# Canonical genuine hand gestures ---------------------------------------------

def finger_count_trace(n: int = 3, **kw: Any) -> Dict[str, Any]:
    fingers = {1: (1,), 2: (1, 2), 3: (1, 2, 3), 4: (1, 2, 3, 4), 5: (0, 1, 2, 3, 4)}[n]
    return hand_trace([(0, {"open_fingers": ()}), (300, {"open_fingers": fingers}), (1200, {"open_fingers": fingers})], **kw)


def wave_trace(**kw: Any) -> Dict[str, Any]:
    return hand_trace(
        [(0, {"wx": 0.5}), (250, {"wx": 0.35}), (500, {"wx": 0.65}), (750, {"wx": 0.35}), (1000, {"wx": 0.65}), (1250, {"wx": 0.5})],
        **kw,
    )


def flip_trace(**kw: Any) -> Dict[str, Any]:
    return hand_trace([(0, {}), (400, {}), (440, {"flip": True}), (900, {"flip": True})], **kw)


def tap_trace(**kw: Any) -> Dict[str, Any]:
    return hand_trace(
        [(0, {"pinch": 0.0}), (200, {"pinch": 0.0}), (320, {"pinch": 1.0}), (400, {"pinch": 1.0}), (520, {"pinch": 0.0}), (700, {"pinch": 0.0})],
        **kw,
    )


def pinch_trace(**kw: Any) -> Dict[str, Any]:
    return hand_trace([(0, {"pinch": 0.0}), (300, {"pinch": 0.0}), (450, {"pinch": 1.0}), (1400, {"pinch": 1.0})], **kw)


def peek_trace(**kw: Any) -> Dict[str, Any]:
    return hand_trace([(0, {"wy": 0.55}), (900, {"wy": 0.55}), (940, None), (1500, None)], **kw)


def hold_trace(**kw: Any) -> Dict[str, Any]:
    return hand_trace([(0, {}), (1000, {})], **kw)
