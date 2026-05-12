"""Integration tests for /liveness/verify-challenge (Bug 4, 2026-05-12).

The endpoint exists to give the web biometric-puzzles training surface a
server round-trip it MUST wait on before resolving its `onSuccess()`. The
checks are structural — full ML re-detection belongs to the multi-step
/liveness/verify flow.

Each test pins one behavior:
  * Happy path with sane inputs → 200, verified=true.
  * Inverted timestamps → 200, verified=false (TIMESTAMPS_OUT_OF_ORDER).
  * Duration < min → 200, verified=false (DURATION_TOO_SHORT).
  * Duration > max → 200, verified=false (DURATION_TOO_LONG).
  * Confidence below floor → 200, verified=false (CONFIDENCE_BELOW_FLOOR).
  * Unknown action enum → 422 (FastAPI validation).
"""

from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest

# Mock heavy ML deps before importing the app (matches the
# test_verify_antispoof_block_enforce.py / test_verify_antispoof_wiring.py
# convention — see those files' module-docstrings for context).
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())
sys.modules.setdefault("resemblyzer", Mock(VoiceEncoder=Mock()))

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _payload(**overrides) -> dict:
    """Build a baseline-valid payload; override fields per test."""
    base = {
        "action": "blink",
        "start_timestamp_ms": 1_000_000.0,
        "end_timestamp_ms": 1_000_500.0,  # +500ms
        "confidence": 0.85,
        "tenant_id": "tenant-x",
        "user_id": "user-y",
        "metrics": {"min_ear": 0.12},
    }
    base.update(overrides)
    return base


def test_happy_path_returns_verified_true(client: TestClient) -> None:
    resp = client.post("/api/v1/liveness/verify-challenge", json=_payload())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "blink"
    assert 0.49 < body["duration_seconds"] < 0.51
    assert body["reason_code"] is None


def test_inverted_timestamps_reject(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(start_timestamp_ms=2_000_000.0, end_timestamp_ms=1_999_000.0),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "TIMESTAMPS_OUT_OF_ORDER"


def test_duration_too_short_reject(client: TestClient) -> None:
    # 50ms — below the 120ms floor.
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(start_timestamp_ms=1_000_000.0, end_timestamp_ms=1_000_050.0),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "DURATION_TOO_SHORT"


def test_duration_too_long_reject(client: TestClient) -> None:
    # 65s — above the 60s ceiling.
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(start_timestamp_ms=1_000_000.0, end_timestamp_ms=1_065_000.0),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "DURATION_TOO_LONG"


def test_confidence_below_floor_reject(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(confidence=0.3),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is False
    assert body["reason_code"] == "CONFIDENCE_BELOW_FLOOR"


def test_unknown_action_is_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(action="not_a_real_challenge"),
    )
    # FastAPI/Pydantic enum validation → 422.
    assert resp.status_code == 422, resp.text


def test_gesture_action_accepted(client: TestClient) -> None:
    """Hand-modality actions (pinch, hand_flip, finger_count, ...) must
    pass the structural checks the same as face actions."""
    resp = client.post(
        "/api/v1/liveness/verify-challenge",
        json=_payload(action="pinch", end_timestamp_ms=1_002_000.0),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["action"] == "pinch"
