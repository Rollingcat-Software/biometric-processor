"""Metric-based challenge scoring (face + hand), shared by the puzzle paths.

Single source of truth for the per-action plausibility gates used by BOTH:

  * the stateless ``POST /liveness/verify-challenge`` training surface
    (face metrics only, metric-OPTIONAL — absent metric passes for back-compat); and
  * the server-issued, anti-replay ``POST /liveness/puzzle-session/{id}/challenge``
    auth path (face + hand, metric-REQUIRED — absent/empty metric fails, closing the
    "structural-only passes" hole).

The client computes the per-action metric locally (MediaPipe FaceMesh for the 14
face challenges; MediaPipe Hands for the 9 hand challenges) and submits a small
scalar payload. The server applies a deterministic threshold gate. No frame
streaming, no ML inference on the server — the gate mirrors the thresholds the
session-based detectors use:

  Face (mirrors ``ActiveLivenessManager`` / ``LiveSessionBaselineCalibrator``):
    blink / close_left_eye / close_right_eye   ear            ≤ 0.21
    smile                                       mar            ≥ 0.40
    open_mouth                                  mar            ≥ 0.50
    raise_eyebrows / raise_left_brow /          brow_raise     ≥ 0.08
      raise_right_brow
    turn_left                                   yaw            ≤ -15.0°
    turn_right                                  yaw            ≥ +15.0°
    look_up                                     pitch          ≤ -10.0°
    look_down                                   pitch          ≥ +10.0°
    nod / shake_head                            oscillation_count ≥ 2
    light                                       brightness_delta  ≥ 0.05

  Hand (mirrors ``ActiveGestureLivenessManager`` thresholds):
    finger_count / math                         finger_count    == target (in params)
    wave                                         reversals       ≥ 2
    hand_flip                                    orientation_changes ≥ 1
    finger_tap                                   tap_dist_scaled ≤ 0.08
    pinch                                        pinch_dist_scaled ≤ 0.12
    hold_position                                wrist_variance  ≤ 2e-3
    shape_trace                                  dtw_cost        ≤ 0.25
    peek_a_boo                                   covered_then_revealed == True

The gate returns ``None`` on pass, or a ``(reason_code, message)`` tuple on
failure. The puzzle path additionally treats an absent metric as a failure
(``METRIC_REQUIRED``); the verify-challenge path passes through absent metrics.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.api.schemas.active_liveness import ChallengeType

# ---------------------------------------------------------------------------
# Face thresholds (mirror ActiveLivenessManager / verify-challenge / calibrator)
# ---------------------------------------------------------------------------

# EAR ≤ this → eye closed enough (blink_threshold=0.21).
_EYE_CLOSE_EAR_MAX: float = 0.21
# MAR ≥ this → smile/mouth-open confirmed.
_SMILE_MAR_MIN: float = 0.40
_OPEN_MOUTH_MAR_MIN: float = 0.50
# Brow-raise metric ≥ this → confirmed (eyebrow_threshold=0.08).
_BROW_RAISE_MIN: float = 0.08
# |yaw| ≥ this (degrees) → head turn confirmed.
_HEAD_YAW_MIN_DEG: float = 15.0
# |pitch| ≥ this (degrees) → head look up/down confirmed.
_HEAD_PITCH_MIN_DEG: float = 10.0
# Minimum oscillation cycles for nod / shake.
_OSCILLATION_MIN: int = 2
# Brightness delta ≥ this → the screen flash was observed (LIGHT challenge).
_LIGHT_BRIGHTNESS_DELTA_MIN: float = 0.05

# ---------------------------------------------------------------------------
# Hand thresholds (mirror ActiveGestureLivenessManager defaults)
# ---------------------------------------------------------------------------

_WAVE_MIN_REVERSALS: int = 2
_HAND_FLIP_MIN_ORIENT_CHANGES: int = 1
_FINGER_TAP_MAX_DIST_SCALED: float = 0.08
_PINCH_MAX_DIST_SCALED: float = 0.12
_HOLD_MAX_VARIANCE: float = 2e-3
_DTW_COST_MAX: float = 0.25


# Metric key documentation, exposed so route schemas / docs / tests can refer to
# the canonical key per action without duplicating string literals.
ACTION_METRIC_KEY: Dict[ChallengeType, str] = {
    ChallengeType.BLINK: "ear",
    ChallengeType.CLOSE_LEFT_EYE: "ear",
    ChallengeType.CLOSE_RIGHT_EYE: "ear",
    ChallengeType.SMILE: "mar",
    ChallengeType.OPEN_MOUTH: "mar",
    ChallengeType.RAISE_EYEBROWS: "brow_raise",
    ChallengeType.RAISE_LEFT_BROW: "brow_raise",
    ChallengeType.RAISE_RIGHT_BROW: "brow_raise",
    ChallengeType.TURN_LEFT: "yaw",
    ChallengeType.TURN_RIGHT: "yaw",
    ChallengeType.LOOK_UP: "pitch",
    ChallengeType.LOOK_DOWN: "pitch",
    ChallengeType.NOD: "oscillation_count",
    ChallengeType.SHAKE_HEAD: "oscillation_count",
    ChallengeType.LIGHT: "brightness_delta",
    ChallengeType.FINGER_COUNT: "finger_count",
    ChallengeType.MATH: "finger_count",
    ChallengeType.WAVE: "reversals",
    ChallengeType.HAND_FLIP: "orientation_changes",
    ChallengeType.FINGER_TAP: "tap_dist_scaled",
    ChallengeType.PINCH: "pinch_dist_scaled",
    ChallengeType.HOLD_POSITION: "wrist_variance",
    ChallengeType.SHAPE_TRACE: "dtw_cost",
    ChallengeType.PEEK_A_BOO: "covered_then_revealed",
}


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def score_action_metrics(
    action: ChallengeType,
    metrics: Dict[str, Any],
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, str]]:
    """Apply the per-action metric plausibility gate.

    Args:
        action: The challenge action being scored.
        metrics: Client-computed metric payload (one scalar per action).
        params: Challenge params issued by the server (e.g. ``target`` for
            finger_count). Optional; only finger_count / math consult it.

    Returns:
        ``None`` if the metric is present AND plausible for the action.
        A ``(reason_code, message)`` tuple if the supplied metric is implausible.
        For actions with no registered metric gate, returns ``None`` (pass).

    Note:
        This function does NOT decide whether an absent metric is acceptable —
        a missing metric returns ``None`` here so the verify-challenge path can
        keep its metric-OPTIONAL behaviour. The puzzle path enforces
        metric-required separately (via :func:`metric_is_present`).
    """
    params = params or {}

    # --- Face: eye-closure (EAR ≤ max) ---
    if action in (
        ChallengeType.BLINK,
        ChallengeType.CLOSE_LEFT_EYE,
        ChallengeType.CLOSE_RIGHT_EYE,
    ):
        ear = _to_float(metrics.get("ear"))
        if ear is not None and ear > _EYE_CLOSE_EAR_MAX:
            return ("EYE_NOT_CLOSED", "Eye EAR is above the closed-eye threshold.")
        return None

    # --- Face: smile (MAR ≥ min) ---
    if action == ChallengeType.SMILE:
        mar = _to_float(metrics.get("mar"))
        if mar is not None and mar < _SMILE_MAR_MIN:
            return ("SMILE_NOT_DETECTED", "Mouth-aspect ratio below the smile threshold.")
        return None

    # --- Face: open mouth (MAR ≥ min, stricter) ---
    if action == ChallengeType.OPEN_MOUTH:
        mar = _to_float(metrics.get("mar"))
        if mar is not None and mar < _OPEN_MOUTH_MAR_MIN:
            return ("MOUTH_NOT_OPEN", "Mouth-aspect ratio below the open-mouth threshold.")
        return None

    # --- Face: brow raise (≥ min) ---
    if action in (
        ChallengeType.RAISE_EYEBROWS,
        ChallengeType.RAISE_LEFT_BROW,
        ChallengeType.RAISE_RIGHT_BROW,
    ):
        brow = _to_float(metrics.get("brow_raise"))
        if brow is not None and brow < _BROW_RAISE_MIN:
            return ("BROW_NOT_RAISED", "Brow-raise metric below the acceptance threshold.")
        return None

    # --- Face: head yaw (turn) ---
    if action == ChallengeType.TURN_LEFT:
        yaw = _to_float(metrics.get("yaw"))
        if yaw is not None and yaw > -_HEAD_YAW_MIN_DEG:
            return ("INSUFFICIENT_HEAD_YAW", "Head yaw does not confirm a left turn.")
        return None
    if action == ChallengeType.TURN_RIGHT:
        yaw = _to_float(metrics.get("yaw"))
        if yaw is not None and yaw < _HEAD_YAW_MIN_DEG:
            return ("INSUFFICIENT_HEAD_YAW", "Head yaw does not confirm a right turn.")
        return None

    # --- Face: head pitch (look up/down) ---
    if action == ChallengeType.LOOK_UP:
        pitch = _to_float(metrics.get("pitch"))
        if pitch is not None and pitch > -_HEAD_PITCH_MIN_DEG:
            return ("INSUFFICIENT_HEAD_PITCH", "Head pitch does not confirm a look-up gesture.")
        return None
    if action == ChallengeType.LOOK_DOWN:
        pitch = _to_float(metrics.get("pitch"))
        if pitch is not None and pitch < _HEAD_PITCH_MIN_DEG:
            return ("INSUFFICIENT_HEAD_PITCH", "Head pitch does not confirm a look-down gesture.")
        return None

    # --- Face: nod / shake (oscillation) ---
    if action in (ChallengeType.NOD, ChallengeType.SHAKE_HEAD):
        osc = _to_int(metrics.get("oscillation_count"))
        if osc is not None and osc < _OSCILLATION_MIN:
            return (
                "INSUFFICIENT_OSCILLATION",
                "Head oscillation count below the minimum for this gesture.",
            )
        return None

    # --- Face: light flash ---
    if action == ChallengeType.LIGHT:
        delta = _to_float(metrics.get("brightness_delta"))
        if delta is not None and delta < _LIGHT_BRIGHTNESS_DELTA_MIN:
            return ("LIGHT_NOT_OBSERVED", "Screen-flash brightness delta below the threshold.")
        return None

    # --- Hand: finger count / math (must match the issued target) ---
    if action in (ChallengeType.FINGER_COUNT, ChallengeType.MATH):
        observed = _to_int(metrics.get("finger_count"))
        target = _to_int(params.get("target"))
        if observed is not None and target is not None and observed != target:
            return (
                "FINGER_COUNT_MISMATCH",
                f"Observed {observed} fingers; expected {target}.",
            )
        return None

    # --- Hand: wave (reversals ≥ min) ---
    if action == ChallengeType.WAVE:
        reversals = _to_int(metrics.get("reversals"))
        if reversals is not None and reversals < _WAVE_MIN_REVERSALS:
            return ("INSUFFICIENT_WAVE", "Wave reversal count below the minimum.")
        return None

    # --- Hand: hand flip (orientation changes ≥ min) ---
    if action == ChallengeType.HAND_FLIP:
        changes = _to_int(metrics.get("orientation_changes"))
        if changes is not None and changes < _HAND_FLIP_MIN_ORIENT_CHANGES:
            return ("HAND_NOT_FLIPPED", "Hand orientation did not change.")
        return None

    # --- Hand: finger tap (tip distance ≤ max) ---
    if action == ChallengeType.FINGER_TAP:
        dist = _to_float(metrics.get("tap_dist_scaled"))
        if dist is not None and dist > _FINGER_TAP_MAX_DIST_SCALED:
            return ("TAP_NOT_DETECTED", "Fingertip distance above the tap threshold.")
        return None

    # --- Hand: pinch (thumb-index distance ≤ max) ---
    if action == ChallengeType.PINCH:
        dist = _to_float(metrics.get("pinch_dist_scaled"))
        if dist is not None and dist > _PINCH_MAX_DIST_SCALED:
            return ("PINCH_NOT_DETECTED", "Thumb-index distance above the pinch threshold.")
        return None

    # --- Hand: hold position (wrist variance ≤ max) ---
    if action == ChallengeType.HOLD_POSITION:
        var = _to_float(metrics.get("wrist_variance"))
        if var is not None and var > _HOLD_MAX_VARIANCE:
            return ("HAND_NOT_STILL", "Wrist variance above the hold-still threshold.")
        return None

    # --- Hand: shape trace (DTW cost ≤ max) ---
    if action == ChallengeType.SHAPE_TRACE:
        cost = _to_float(metrics.get("dtw_cost"))
        if cost is not None and cost > _DTW_COST_MAX:
            return ("SHAPE_MISMATCH", "Shape-trace DTW cost above the match threshold.")
        return None

    # --- Hand: peek-a-boo (covered then revealed flag) ---
    if action == ChallengeType.PEEK_A_BOO:
        flag = metrics.get("covered_then_revealed")
        if flag is not None and not bool(flag):
            return ("PEEK_A_BOO_INCOMPLETE", "Did not observe a cover-then-reveal sequence.")
        return None

    # No registered gate for this action — pass.
    return None


def metric_is_present(action: ChallengeType, metrics: Dict[str, Any]) -> bool:
    """Return True if the canonical metric for ``action`` is present (non-empty).

    Used by the metric-REQUIRED puzzle path to close the structural-only hole.
    An empty ``metrics`` dict, or one missing the action's canonical key (or with
    a ``None`` value for it), is treated as absent.
    """
    if not metrics:
        return False
    key = ACTION_METRIC_KEY.get(action)
    if key is None:
        # Action has no registered metric — require at least one non-null metric.
        return any(v is not None for v in metrics.values())
    return metrics.get(key) is not None


__all__ = [
    "score_action_metrics",
    "metric_is_present",
    "ACTION_METRIC_KEY",
]
