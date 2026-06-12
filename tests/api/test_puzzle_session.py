"""Tests for the server-issued, single-use, anti-replay puzzle SESSION (CV-1).

Routes under test (mounted on a minimal FastAPI app to avoid the heavy app
lifespan, mirroring tests/api/test_puzzle_verify_challenge.py):

  POST /api/v1/liveness/puzzle-session
  POST /api/v1/liveness/puzzle-session/{session_id}/challenge
  POST /api/v1/liveness/puzzle-session/{session_id}/verdict

Contract: docs/superpowers/plans/2026-06-12-puzzle-session-convergence.md.

Coverage:
  * create → returns session_id + exactly `count` server-chosen challenges,
    all drawn from the allowed set;
  * submit a valid challenge → verified:true + marked complete;
  * submit with absent metric → verified:false (METRIC_REQUIRED);
  * submit an action NOT in the issued set → rejected (ACTION_NOT_ISSUED);
  * verdict before all complete → verified:false;
  * verdict after all valid → verified:true, THEN a second verdict → false
    (single-use / consumed);
  * verdict with wrong user_id/tenant_id → false (owner binding);
  * expired session → false / 404;
  * the session spans both face and hand challenge types.
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import puzzle as puzzle_routes
from app.api.routes.puzzle import get_puzzle_session_manager, router as puzzle_router

_USER = "user-aaa"
_TENANT = "tenant-xyz"

# Valid metric payloads, one per action used in these tests.
_VALID_METRICS = {
    "close_left_eye": {"ear": 0.12},
    "close_right_eye": {"ear": 0.10},
    "smile": {"mar": 0.55},
    "nod": {"oscillation_count": 3},
    "wave": {"reversals": 3},
    "pinch": {"pinch_dist_scaled": 0.05},
    "look_up": {"pitch": -15.0},
}

_BASE_START = 1_000_000.0
_BASE_END = 1_001_000.0


@pytest.fixture()
def client() -> TestClient:
    """Fresh app + fresh manager singleton per test (single-use isolation)."""
    get_puzzle_session_manager.cache_clear()
    app = FastAPI()
    app.include_router(puzzle_router, prefix="/api/v1")
    return TestClient(app)


def _manager():
    return get_puzzle_session_manager()


def _create(client: TestClient, allowed, count, user=_USER, tenant=_TENANT) -> dict:
    resp = client.post(
        "/api/v1/liveness/puzzle-session",
        json={
            "tenant_id": tenant,
            "user_id": user,
            "allowed_challenge_types": allowed,
            "count": count,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _submit(client: TestClient, sid: str, action: str, metrics=None) -> dict:
    body = {
        "action": action,
        "metrics": metrics if metrics is not None else _VALID_METRICS.get(action, {}),
        "start_timestamp_ms": _BASE_START,
        "end_timestamp_ms": _BASE_END,
        "confidence": 0.9,
    }
    return client.post(
        f"/api/v1/liveness/puzzle-session/{sid}/challenge", json=body
    )


def _verdict(client: TestClient, sid: str, user=_USER, tenant=_TENANT):
    return client.post(
        f"/api/v1/liveness/puzzle-session/{sid}/verdict",
        json={"user_id": user, "tenant_id": tenant},
    )


def _complete_all(client: TestClient, sid: str) -> None:
    """Submit a valid metric for every issued challenge in the session."""
    session = _manager().get_session(sid)
    assert session is not None
    for ch in session.challenges:
        resp = _submit(client, sid, ch.action.value)
        assert resp.status_code == 200, resp.text
        assert resp.json()["verified"] is True, resp.json()


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


def test_create_returns_session_id_and_count_challenges(client: TestClient) -> None:
    allowed = ["close_left_eye", "smile", "nod", "wave", "pinch"]
    data = _create(client, allowed, count=3)
    assert isinstance(data["session_id"], str) and len(data["session_id"]) >= 20
    assert len(data["challenges"]) == 3
    # Every issued challenge is drawn from the allowed set.
    for ch in data["challenges"]:
        assert ch["action"] in allowed


def test_create_spans_face_and_hand(client: TestClient) -> None:
    """A single session can issue both face and hand challenge types."""
    allowed = ["close_left_eye", "smile", "nod", "wave", "pinch"]
    # Ask for all 5 distinct types so both modalities are represented.
    data = _create(client, allowed, count=5)
    actions = {c["action"] for c in data["challenges"]}
    face = {"close_left_eye", "smile", "nod"}
    hand = {"wave", "pinch"}
    assert actions & face, "expected at least one face challenge"
    assert actions & hand, "expected at least one hand challenge"


def test_create_finger_count_carries_target_param(client: TestClient) -> None:
    data = _create(client, ["finger_count"], count=1)
    params = data["challenges"][0]["params"]
    assert params is not None and 1 <= params["target"] <= 5


def test_create_empty_allowed_is_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/puzzle-session",
        json={
            "tenant_id": _TENANT,
            "user_id": _USER,
            "allowed_challenge_types": [],
            "count": 1,
        },
    )
    assert resp.status_code == 422  # min_length=1 schema validation


# ---------------------------------------------------------------------------
# SUBMIT
# ---------------------------------------------------------------------------


def test_submit_valid_challenge_verifies_and_marks_complete(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    action = data["challenges"][0]["action"]
    resp = _submit(client, sid, action)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == action
    assert body["reason_code"] is None
    # Marked complete in the session.
    ch = _manager().get_session(sid).challenges[0]
    assert ch.completed is True and ch.verified is True


def test_submit_absent_metric_fails(client: TestClient) -> None:
    data = _create(client, ["smile"], count=1)
    sid = data["session_id"]
    resp = _submit(client, sid, "smile", metrics={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "METRIC_REQUIRED"


def test_submit_action_not_issued_rejected(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    # "pinch" was not issued for this session.
    assert all(c["action"] != "pinch" for c in data["challenges"])
    resp = _submit(client, sid, "pinch")
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "ACTION_NOT_ISSUED"


def test_submit_implausible_metric_fails(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    # EAR above the closed-eye threshold → eye still open.
    resp = _submit(client, sid, "close_left_eye", metrics={"ear": 0.30})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "EYE_NOT_CLOSED"


def test_submit_same_challenge_twice_already_completed(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    assert _submit(client, sid, "close_left_eye").json()["verified"] is True
    resp = _submit(client, sid, "close_left_eye")
    assert resp.json()["verified"] is False
    assert resp.json()["reason_code"] == "ALREADY_COMPLETED"


def test_submit_unknown_session_404(client: TestClient) -> None:
    resp = _submit(client, "does-not-exist", "smile")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# VERDICT
# ---------------------------------------------------------------------------


def test_verdict_before_all_complete_is_false(client: TestClient) -> None:
    data = _create(client, ["close_left_eye", "smile"], count=2)
    sid = data["session_id"]
    # Complete only the first issued challenge.
    first = data["challenges"][0]["action"]
    assert _submit(client, sid, first).json()["verified"] is True
    resp = _verdict(client, sid)
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


def test_verdict_after_all_valid_then_single_use(client: TestClient) -> None:
    data = _create(client, ["close_left_eye", "smile", "nod"], count=3)
    sid = data["session_id"]
    _complete_all(client, sid)
    first = _verdict(client, sid)
    assert first.status_code == 200
    assert first.json()["verified"] is True
    # Single-use: the session is consumed → a second verdict is gone (404).
    second = _verdict(client, sid)
    assert second.status_code == 404


def test_verdict_wrong_user_is_false(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    _complete_all(client, sid)
    resp = _verdict(client, sid, user="intruder")
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


def test_verdict_wrong_tenant_is_false(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    _complete_all(client, sid)
    resp = _verdict(client, sid, tenant="other-tenant")
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


def test_verdict_owner_mismatch_also_consumes(client: TestClient) -> None:
    """A failed (owner-mismatch) verdict still consumes the session (anti-replay)."""
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    _complete_all(client, sid)
    bad = _verdict(client, sid, user="intruder")
    assert bad.json()["verified"] is False
    # Even the true owner cannot now verify — the id is consumed.
    again = _verdict(client, sid)
    assert again.status_code == 404


def test_verdict_unknown_session_404(client: TestClient) -> None:
    resp = _verdict(client, "nope")
    assert resp.status_code == 404


def test_expired_session_verdict_404(client: TestClient) -> None:
    data = _create(client, ["close_left_eye"], count=1)
    sid = data["session_id"]
    _complete_all(client, sid)
    # Force expiry by rewinding the stored session's expires_at.
    session = _manager().get_session(sid)
    session.expires_at = time.time() - 1.0
    resp = _verdict(client, sid)
    assert resp.status_code == 404


def test_expired_session_submit_404(client: TestClient) -> None:
    data = _create(client, ["close_left_eye", "smile"], count=2)
    sid = data["session_id"]
    session = _manager().get_session(sid)
    session.expires_at = time.time() - 1.0
    resp = _submit(client, sid, data["challenges"][0]["action"])
    assert resp.status_code == 404
