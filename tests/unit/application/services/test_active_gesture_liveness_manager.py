"""Unit tests for ActiveGestureLivenessManager.

Uses synthetic 21-landmark hand arrays crafted by hand (no MediaPipe runtime),
exercising each detector path and the anti-spoof gate.
"""

from __future__ import annotations

import math
from typing import List

import pytest

from app.api.schemas.active_liveness import (
    ActiveLivenessSession,
    Challenge,
    ChallengeStatus,
    ChallengeType,
)
from app.api.schemas.gesture_liveness import (
    GestureFramePayload,
    GestureLivenessConfig,
    HandLandmark,
)
from app.application.services.active_gesture_liveness_manager import (
    ActiveGestureLivenessManager,
    load_shape_template_catalog,
)


# ---------------------------------------------------------------------------
# Synthetic hand builders
# ---------------------------------------------------------------------------

# MediaPipe Hand Landmarker indices (21 points):
#   0       WRIST
#   1..4    THUMB (CMC, MCP, IP, TIP)
#   5..8    INDEX (MCP, PIP, DIP, TIP)
#   9..12   MIDDLE
#   13..16  RING
#   17..20  PINKY


def _pt(x: float, y: float, z: float = 0.0) -> HandLandmark:
    return HandLandmark(x=x, y=y, z=z)


def make_open_hand(
    cx: float = 0.5, cy: float = 0.5, spread: float = 0.08
) -> List[HandLandmark]:
    """21-point open-palm hand. All five fingers extended upward (-y)."""

    wrist = _pt(cx, cy + 0.12)
    # THUMB tilted out to the left (x-), thumb_tip far from pinky_mcp.
    thumb = [
        _pt(cx - spread * 0.5, cy + 0.06),
        _pt(cx - spread * 1.2, cy + 0.02),
        _pt(cx - spread * 1.8, cy - 0.02),
        _pt(cx - spread * 2.4, cy - 0.05),  # THUMB_TIP far from pinky_mcp
    ]
    # Index finger (up).
    index = [
        _pt(cx - spread, cy + 0.04),      # MCP
        _pt(cx - spread, cy - 0.02),      # PIP
        _pt(cx - spread, cy - 0.08),      # DIP
        _pt(cx - spread, cy - 0.16),      # TIP (far from wrist)
    ]
    middle = [
        _pt(cx, cy + 0.04),
        _pt(cx, cy - 0.02),
        _pt(cx, cy - 0.09),
        _pt(cx, cy - 0.18),
    ]
    ring = [
        _pt(cx + spread, cy + 0.04),
        _pt(cx + spread, cy - 0.02),
        _pt(cx + spread, cy - 0.08),
        _pt(cx + spread, cy - 0.15),
    ]
    pinky = [
        _pt(cx + spread * 2, cy + 0.04),
        _pt(cx + spread * 2, cy - 0.01),
        _pt(cx + spread * 2, cy - 0.05),
        _pt(cx + spread * 2, cy - 0.10),
    ]
    landmarks = [wrist, *thumb, *index, *middle, *ring, *pinky]
    assert len(landmarks) == 21
    return landmarks


def make_fist(cx: float = 0.5, cy: float = 0.5) -> List[HandLandmark]:
    """Closed fist: tips near the wrist, thumb tucked across palm."""

    wrist = _pt(cx, cy + 0.12)
    # Thumb TIP next to pinky MCP → thumb_ratio small.
    thumb = [
        _pt(cx + 0.01, cy + 0.07),
        _pt(cx + 0.015, cy + 0.04),
        _pt(cx + 0.018, cy + 0.025),
        _pt(cx + 0.02, cy + 0.02),  # THUMB_TIP
    ]
    # Index-pinky: TIP close to PIP (finger_ratio near 0).
    index = [
        _pt(cx - 0.02, cy + 0.04),
        _pt(cx - 0.02, cy + 0.02),
        _pt(cx - 0.02, cy + 0.015),
        _pt(cx - 0.02, cy + 0.015),
    ]
    middle = [
        _pt(cx, cy + 0.04),
        _pt(cx, cy + 0.02),
        _pt(cx, cy + 0.015),
        _pt(cx, cy + 0.015),
    ]
    ring = [
        _pt(cx + 0.02, cy + 0.04),
        _pt(cx + 0.02, cy + 0.02),
        _pt(cx + 0.02, cy + 0.015),
        _pt(cx + 0.02, cy + 0.015),
    ]
    pinky = [
        _pt(cx + 0.04, cy + 0.04),
        _pt(cx + 0.04, cy + 0.02),
        _pt(cx + 0.04, cy + 0.015),
        _pt(cx + 0.04, cy + 0.015),
    ]
    landmarks = [wrist, *thumb, *index, *middle, *ring, *pinky]
    assert len(landmarks) == 21
    return landmarks


def make_peace_sign(cx: float = 0.5, cy: float = 0.5) -> List[HandLandmark]:
    """Index + middle extended, ring + pinky curled, thumb tucked."""

    base = make_fist(cx, cy)
    # Extend index (indices 5..8)
    base[5] = _pt(cx - 0.04, cy + 0.03)
    base[6] = _pt(cx - 0.04, cy - 0.02)
    base[7] = _pt(cx - 0.04, cy - 0.08)
    base[8] = _pt(cx - 0.04, cy - 0.16)
    # Extend middle (indices 9..12)
    base[9] = _pt(cx, cy + 0.03)
    base[10] = _pt(cx, cy - 0.03)
    base[11] = _pt(cx, cy - 0.09)
    base[12] = _pt(cx, cy - 0.18)
    return base


def make_pinch(cx: float = 0.5, cy: float = 0.5) -> List[HandLandmark]:
    """Thumb tip + index tip touching at the same point."""

    lms = make_open_hand(cx, cy)
    touch = _pt(cx, cy - 0.10)
    lms[4] = touch   # THUMB_TIP
    lms[8] = touch   # INDEX_TIP (same point)
    # Also set z values close so _detect_pinch's z gate passes.
    lms[4] = HandLandmark(x=cx, y=cy - 0.10, z=0.0)
    lms[8] = HandLandmark(x=cx, y=cy - 0.10, z=0.0)
    return lms


def make_finger_tap(cx: float = 0.5, cy: float = 0.5) -> List[HandLandmark]:
    """Index tip and middle tip touching."""

    lms = make_open_hand(cx, cy)
    touch = _pt(cx - 0.002, cy - 0.14)
    touch2 = _pt(cx + 0.002, cy - 0.14)
    lms[8] = touch     # INDEX_TIP
    lms[12] = touch2   # MIDDLE_TIP (very close)
    return lms


def _frame(
    landmarks_right=None,
    landmarks_left=None,
    *,
    frame_time_ms=0,
    tremor=0.01,
    brightness=0.5,
    face_covered=None,
) -> GestureFramePayload:
    return GestureFramePayload(
        frame_time_ms=frame_time_ms,
        landmarks_right=landmarks_right,
        landmarks_left=landmarks_left,
        tremor_variance=tremor,
        brightness_std=brightness,
        face_covered=face_covered,
    )


def _build_session(manager: ActiveGestureLivenessManager, challenge: Challenge) -> ActiveLivenessSession:
    """Build a session with a single challenge already in progress."""

    now = 1_000.0
    session = ActiveLivenessSession(
        session_id="test-session",
        modality="gesture",
        challenges=[challenge],
        current_challenge_index=0,
        started_at=now,
        expires_at=now + 120,
        last_activity_at=now,
        current_challenge_started_at=now,
        gesture_state={"per_challenge": {}},
    )
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_creates_gesture_session_with_requested_challenges(self):
        m = ActiveGestureLivenessManager()
        cfg = GestureLivenessConfig(
            num_challenges=3,
            required_gesture_challenges=None,
            randomize=False,
            challenge_timeout=10.0,
            session_timeout_seconds=60.0,
        )
        s = m.create_session(cfg)
        assert s.modality == "gesture"
        assert len(s.challenges) == 3
        assert all(c.status == ChallengeStatus.PENDING for c in s.challenges)
        assert "per_challenge" in s.gesture_state

    def test_widens_base_config(self):
        from app.api.schemas.active_liveness import ActiveLivenessConfig

        m = ActiveGestureLivenessManager()
        s = m.create_session(ActiveLivenessConfig(num_challenges=1))
        assert s.modality == "gesture"
        assert len(s.challenges) == 1


class TestAntiSpoof:
    @pytest.mark.asyncio
    async def test_rejects_low_tremor(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.FINGER_COUNT, instruction="")
        s = _build_session(m, ch)
        s.gesture_state["per_challenge"]["0"] = {"target": 2, "matched_frames": 0}
        frame = _frame(
            landmarks_right=make_peace_sign(),
            tremor=1e-6,  # below DEFAULT_TREMOR_VARIANCE_MIN (3e-4)
            brightness=0.5,
        )
        resp = await m.process_frame(s, frame)
        assert resp.detection is not None
        assert resp.detection.detected is False
        assert resp.detection.details.get("anti_spoof_rejected") is True

    @pytest.mark.asyncio
    async def test_rejects_low_brightness(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.FINGER_COUNT, instruction="")
        s = _build_session(m, ch)
        s.gesture_state["per_challenge"]["0"] = {"target": 2, "matched_frames": 0}
        frame = _frame(
            landmarks_right=make_peace_sign(),
            tremor=0.01,
            brightness=1e-6,  # below DEFAULT_BRIGHTNESS_STD_MIN (0.05)
        )
        resp = await m.process_frame(s, frame)
        assert resp.detection.details.get("anti_spoof_rejected") is True


class TestFingerCount:
    @pytest.mark.asyncio
    async def test_peace_sign_detected_as_two_after_three_frames(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.FINGER_COUNT, instruction="")
        s = _build_session(m, ch)
        s.gesture_state["per_challenge"]["0"] = {"target": 2, "matched_frames": 0}
        frame = _frame(landmarks_right=make_peace_sign())
        # First two frames: accumulating.
        r1 = await m.process_frame(s, frame)
        assert r1.detection.detected is False
        r2 = await m.process_frame(s, frame)
        assert r2.detection.detected is False
        # Third frame confirms.
        r3 = await m.process_frame(s, frame)
        assert r3.detection.detected is True
        assert s.challenges[0].status == ChallengeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_fist_not_matched_against_target_two(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.FINGER_COUNT, instruction="")
        s = _build_session(m, ch)
        s.gesture_state["per_challenge"]["0"] = {"target": 2, "matched_frames": 0}
        for _ in range(4):
            resp = await m.process_frame(s, _frame(landmarks_right=make_fist()))
        assert resp.detection.detected is False
        assert s.challenges[0].status != ChallengeStatus.COMPLETED


class TestFingerTap:
    @pytest.mark.asyncio
    async def test_touching_tips_detected(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.FINGER_TAP, instruction="")
        s = _build_session(m, ch)
        frame = _frame(landmarks_right=make_finger_tap())
        r1 = await m.process_frame(s, frame)
        assert r1.detection.detected is False  # one frame not enough
        r2 = await m.process_frame(s, frame)
        assert r2.detection.detected is True


class TestPinch:
    @pytest.mark.asyncio
    async def test_thumb_index_touching_detected(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.PINCH, instruction="")
        s = _build_session(m, ch)
        frame = _frame(landmarks_right=make_pinch())
        r1 = await m.process_frame(s, frame)
        assert r1.detection.detected is False
        r2 = await m.process_frame(s, frame)
        assert r2.detection.detected is True


class TestHoldPosition:
    @pytest.mark.asyncio
    async def test_static_hand_detected_after_window(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.HOLD_POSITION, instruction="")
        s = _build_session(m, ch)
        # Same landmarks: require >=15 frames in the window.
        detected_frame: int | None = None
        for i in range(20):
            resp = await m.process_frame(
                s, _frame(landmarks_right=make_open_hand(), frame_time_ms=i * 33)
            )
            if resp.detection is not None and resp.detection.detected:
                detected_frame = i
                break
        assert detected_frame is not None, "HOLD_POSITION should detect within 20 frames"
        assert s.challenges[0].status == ChallengeStatus.COMPLETED


class TestWave:
    @pytest.mark.asyncio
    async def test_oscillating_wrist_detected(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.WAVE, instruction="")
        s = _build_session(m, ch)
        # Generate a 2Hz oscillation over ~1.5 s with amplitude 0.3.
        detected = False
        for i in range(30):
            t_s = i * 0.05  # 20 fps
            x = 0.5 + 0.15 * math.sin(2 * math.pi * 2.0 * t_s)
            lms = make_open_hand(cx=x, cy=0.5)
            resp = await m.process_frame(
                s,
                _frame(landmarks_right=lms, frame_time_ms=int(t_s * 1000)),
            )
            if resp.detection is not None and resp.detection.detected:
                detected = True
                break
        assert detected, "WAVE should detect a 2Hz oscillation within 1.5s"
        assert s.challenges[0].status == ChallengeStatus.COMPLETED


class TestHandFlip:
    @pytest.mark.asyncio
    async def test_sign_change_detected(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.HAND_FLIP, instruction="")
        s = _build_session(m, ch)
        # Frame A: palm forward (index_mcp to left of wrist, pinky to right => positive cross_z)
        palm_front = make_open_hand(cx=0.5, cy=0.5)
        # Frame B: hand flipped — swap index and pinky MCPs.
        palm_back = make_open_hand(cx=0.5, cy=0.5)
        palm_back[5], palm_back[17] = palm_back[17], palm_back[5]
        await m.process_frame(s, _frame(landmarks_right=palm_front, frame_time_ms=0))
        resp = await m.process_frame(
            s, _frame(landmarks_right=palm_back, frame_time_ms=33)
        )
        assert resp.detection.detected is True


class TestPeekABoo:
    @pytest.mark.asyncio
    async def test_sequence_covered_then_revealed(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.PEEK_A_BOO, instruction="")
        s = _build_session(m, ch)
        # Covered → revealed.
        r1 = await m.process_frame(
            s,
            _frame(landmarks_right=make_open_hand(), face_covered=True, frame_time_ms=0),
        )
        assert r1.detection.detected is False
        r2 = await m.process_frame(
            s,
            _frame(landmarks_right=make_open_hand(), face_covered=False, frame_time_ms=33),
        )
        assert r2.detection.detected is True

    @pytest.mark.asyncio
    async def test_missing_client_flag_rejects(self):
        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.PEEK_A_BOO, instruction="")
        s = _build_session(m, ch)
        resp = await m.process_frame(
            s, _frame(landmarks_right=make_open_hand(), face_covered=None)
        )
        assert resp.detection.detected is False
        assert resp.detection.details.get("error") == "client_face_covered_flag_missing"


class TestShapeTrace:
    @pytest.mark.asyncio
    async def test_circle_trace_detected(self, tmp_path, monkeypatch):
        # Seed the catalog cache with a fresh load.
        catalog = load_shape_template_catalog()
        circle = next(t for t in catalog.templates if t.key == "circle")

        m = ActiveGestureLivenessManager()
        ch = Challenge(type=ChallengeType.SHAPE_TRACE, instruction="")
        s = _build_session(m, ch)
        s.gesture_state["per_challenge"]["0"] = {"template_key": "circle", "trace": []}

        # Trace along the circle template (deterministic detection).
        detected = False
        for i, (x, y) in enumerate(circle.points):
            lms = make_open_hand()
            # Override the index tip to sit on the circle path.
            lms[8] = HandLandmark(x=float(x), y=float(y), z=0.0)
            resp = await m.process_frame(
                s, _frame(landmarks_right=lms, frame_time_ms=i * 33)
            )
            if resp.detection is not None and resp.detection.detected:
                detected = True
                break
        assert detected, "SHAPE_TRACE should match a perfect circle trace"


class TestShapeTemplateCatalog:
    def test_catalog_loads_four_templates(self):
        cat = load_shape_template_catalog()
        keys = {t.key for t in cat.templates}
        assert keys == {"circle", "square", "triangle", "s_curve"}
        assert cat.version.startswith("mtime-")
