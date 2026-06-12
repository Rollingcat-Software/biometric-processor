"""Tests for POST /api/v1/liveness/verify-challenge — 8 new face challenges.

Covers:
  - All 8 new action identifiers (close_left_eye, close_right_eye, look_up,
    look_down, raise_left_brow, raise_right_brow, nod, shake_head) return
    verified=true with valid timing, confidence, and metrics.
  - Each new action's per-metric rejection path returns verified=false with
    the correct reason_code when an implausible metric is supplied.
  - Absent metrics are not penalised (backward-compat gate).
  - The structural checks (timestamps, duration, confidence) still apply to
    the new actions; one representative check per class is included.
  - The 6 pre-existing challenge types (blink, smile, turn_left, turn_right,
    pinch, open_mouth) still pass — regression guard.

Design: the puzzle router is mounted on a minimal FastAPI app without the full
app lifespan (no torch / uniface ONNX pre-load). This keeps the test runnable
on bare CI runners and in the lightweight unit-test environment.  The same
isolation pattern is used by tests/unit/test_nfc_verify_authenticity_route.py.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.puzzle import router as puzzle_router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(puzzle_router, prefix="/api/v1")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

_BASE_START = 1_000_000.0
_BASE_END = 1_001_000.0  # +1 000 ms — well within [120 ms, 60 s]
_BASE_CONFIDENCE = 0.85


def _payload(action: str, **overrides) -> dict:
    """Build a structurally-valid payload; override fields per test."""
    base: dict = {
        "action": action,
        "start_timestamp_ms": _BASE_START,
        "end_timestamp_ms": _BASE_END,
        "confidence": _BASE_CONFIDENCE,
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "metrics": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Regression: existing 6 challenges still pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    ["blink", "smile", "turn_left", "turn_right", "open_mouth", "pinch"],
)
def test_existing_challenges_still_pass(client: TestClient, action: str) -> None:
    resp = client.post("/api/v1/liveness/verify-challenge", json=_payload(action))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True, f"existing action {action!r} unexpectedly rejected: {body}"
    assert body["reason_code"] is None


# ---------------------------------------------------------------------------
# Happy-path: 8 new actions with valid metrics
# ---------------------------------------------------------------------------


def test_close_left_eye_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("close_left_eye", metrics={"ear": 0.15}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "close_left_eye"
    assert body["reason_code"] is None


def test_close_right_eye_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("close_right_eye", metrics={"ear": 0.10}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "close_right_eye"
    assert body["reason_code"] is None


def test_look_up_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("look_up", metrics={"pitch": -15.0}),  # negative = face tilts up
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "look_up"
    assert body["reason_code"] is None


def test_look_down_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("look_down", metrics={"pitch": 12.0}),  # positive = face tilts down
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "look_down"
    assert body["reason_code"] is None


def test_raise_left_brow_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("raise_left_brow", metrics={"brow_raise": 0.12}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "raise_left_brow"
    assert body["reason_code"] is None


def test_raise_right_brow_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("raise_right_brow", metrics={"brow_raise": 0.09}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "raise_right_brow"
    assert body["reason_code"] is None


def test_nod_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("nod", metrics={"oscillation_count": 3}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "nod"
    assert body["reason_code"] is None


def test_shake_head_valid(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("shake_head", metrics={"oscillation_count": 4}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "shake_head"
    assert body["reason_code"] is None


# ---------------------------------------------------------------------------
# Metric-gate rejections: bad metrics → verified=false + correct reason_code
# ---------------------------------------------------------------------------


def test_close_left_eye_ear_too_high(client: TestClient) -> None:
    """EAR above threshold means the eye is still open."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("close_left_eye", metrics={"ear": 0.30}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "EYE_NOT_CLOSED"
    assert body["action"] == "close_left_eye"


def test_close_right_eye_ear_too_high(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("close_right_eye", metrics={"ear": 0.25}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "EYE_NOT_CLOSED"
    assert body["action"] == "close_right_eye"


def test_look_up_pitch_too_shallow(client: TestClient) -> None:
    """Pitch of -5° is too small to confirm a look-up."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("look_up", metrics={"pitch": -5.0}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "INSUFFICIENT_HEAD_PITCH"
    assert body["action"] == "look_up"


def test_look_up_positive_pitch_rejected(client: TestClient) -> None:
    """A positive pitch while claiming look_up is a wrong-direction gesture."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("look_up", metrics={"pitch": 8.0}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "INSUFFICIENT_HEAD_PITCH"


def test_look_down_pitch_too_shallow(client: TestClient) -> None:
    """Pitch of +3° is too small to confirm a look-down."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("look_down", metrics={"pitch": 3.0}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "INSUFFICIENT_HEAD_PITCH"
    assert body["action"] == "look_down"


def test_look_down_negative_pitch_rejected(client: TestClient) -> None:
    """A negative pitch while claiming look_down is a wrong-direction gesture."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("look_down", metrics={"pitch": -11.0}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "INSUFFICIENT_HEAD_PITCH"


def test_raise_left_brow_not_raised(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("raise_left_brow", metrics={"brow_raise": 0.03}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "BROW_NOT_RAISED"
    assert body["action"] == "raise_left_brow"


def test_raise_right_brow_not_raised(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("raise_right_brow", metrics={"brow_raise": 0.00}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "BROW_NOT_RAISED"
    assert body["action"] == "raise_right_brow"


def test_nod_insufficient_oscillation(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("nod", metrics={"oscillation_count": 1}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "INSUFFICIENT_OSCILLATION"
    assert body["action"] == "nod"


def test_shake_head_insufficient_oscillation(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("shake_head", metrics={"oscillation_count": 0}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "INSUFFICIENT_OSCILLATION"
    assert body["action"] == "shake_head"


# ---------------------------------------------------------------------------
# Absent metrics must NOT cause rejection (backward-compat)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "close_left_eye",
        "close_right_eye",
        "look_up",
        "look_down",
        "raise_left_brow",
        "raise_right_brow",
        "nod",
        "shake_head",
    ],
)
def test_absent_metrics_pass(client: TestClient, action: str) -> None:
    """New actions with no metrics dict pass all structural checks."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(action, metrics={}),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True, (
        f"action {action!r} rejected with absent metrics: {body}"
    )
    assert body["reason_code"] is None


# ---------------------------------------------------------------------------
# Structural checks still apply to new actions
# ---------------------------------------------------------------------------


def test_new_action_timestamps_out_of_order(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(
            "look_up",
            start_timestamp_ms=2_000_000.0,
            end_timestamp_ms=1_999_000.0,
            metrics={"pitch": -20.0},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "TIMESTAMPS_OUT_OF_ORDER"


def test_new_action_duration_too_short(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(
            "nod",
            start_timestamp_ms=1_000_000.0,
            end_timestamp_ms=1_000_050.0,  # 50 ms < 120 ms floor
            metrics={"oscillation_count": 3},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "DURATION_TOO_SHORT"


def test_new_action_confidence_below_floor(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(
            "shake_head",
            confidence=0.2,
            metrics={"oscillation_count": 4},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "CONFIDENCE_BELOW_FLOOR"


def test_new_action_unknown_string_is_422(client: TestClient) -> None:
    """A completely unknown action name must still produce a 422."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload("unknown_face_action"),
    )
    assert resp.status_code == 422, resp.text
