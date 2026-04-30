"""Integration tests for active gesture liveness routes.

Covers:
- Feature-flag gating (404 when disabled).
- End-to-end start → frame → completion.
- Shape-template catalog endpoint + ETag 304 path.

Uses the InMemoryActiveLivenessSessionRepository via FastAPI dependency
overrides so no Redis is required.
"""

from __future__ import annotations

import math
import sys
from typing import List
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

# Mock native/ML deps that aren't installed in minimal CI images.
# Matches tests/integration/test_api_routes.py.
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())
sys.modules.setdefault("cv2", Mock())

from app.api.schemas.active_liveness import ChallengeType
from app.api.schemas.gesture_liveness import HandLandmark
from app.application.services.active_gesture_liveness_manager import (
    ActiveGestureLivenessManager,
)
from app.application.use_cases.process_active_gesture_liveness_frame import (
    ProcessActiveGestureLivenessFrameUseCase,
)
from app.application.use_cases.start_active_gesture_liveness import (
    StartActiveGestureLivenessUseCase,
)
from app.core import container
from app.core.config import settings
from app.infrastructure.persistence.repositories.in_memory_active_liveness_session_repository import (
    InMemoryActiveLivenessSessionRepository,
)
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _open_hand(cx=0.5, cy=0.5) -> List[dict]:
    spread = 0.08

    def p(x, y, z=0.0):
        return {"x": float(x), "y": float(y), "z": float(z)}

    wrist = p(cx, cy + 0.12)
    thumb = [
        p(cx - spread * 0.5, cy + 0.06),
        p(cx - spread * 1.2, cy + 0.02),
        p(cx - spread * 1.8, cy - 0.02),
        p(cx - spread * 2.4, cy - 0.05),
    ]
    index = [
        p(cx - spread, cy + 0.04),
        p(cx - spread, cy - 0.02),
        p(cx - spread, cy - 0.08),
        p(cx - spread, cy - 0.16),
    ]
    middle = [
        p(cx, cy + 0.04),
        p(cx, cy - 0.02),
        p(cx, cy - 0.09),
        p(cx, cy - 0.18),
    ]
    ring = [
        p(cx + spread, cy + 0.04),
        p(cx + spread, cy - 0.02),
        p(cx + spread, cy - 0.08),
        p(cx + spread, cy - 0.15),
    ]
    pinky = [
        p(cx + spread * 2, cy + 0.04),
        p(cx + spread * 2, cy - 0.01),
        p(cx + spread * 2, cy - 0.05),
        p(cx + spread * 2, cy - 0.10),
    ]
    return [wrist, *thumb, *index, *middle, *ring, *pinky]


class TestFeatureFlag:
    def test_start_returns_404_when_flag_off(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ACTIVE_GESTURE_LIVENESS_ENABLED", False)
        r = client.post("/api/v1/liveness/active/gesture/start", json={})
        assert r.status_code == 404

    def test_frame_returns_404_when_flag_off(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ACTIVE_GESTURE_LIVENESS_ENABLED", False)
        r = client.post(
            "/api/v1/liveness/active/gesture/frame",
            json={
                "session_id": "nope",
                "payload": {
                    "frame_time_ms": 0,
                    "landmarks_right": _open_hand(),
                    "landmarks_left": None,
                    "tremor_variance": 0.01,
                    "brightness_std": 0.5,
                },
            },
        )
        assert r.status_code == 404

    def test_shape_templates_returns_404_when_flag_off(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ACTIVE_GESTURE_LIVENESS_ENABLED", False)
        r = client.get("/api/v1/liveness/active/gesture/shape-templates")
        assert r.status_code == 404


@pytest.fixture
def enabled_gesture_backend(monkeypatch):
    """Turn the feature flag on and swap repo/manager to in-memory singletons."""

    monkeypatch.setattr(settings, "ACTIVE_GESTURE_LIVENESS_ENABLED", True)
    # Reset lru_cache so the factory picks up the flip.
    container.clear_cache()

    repo = InMemoryActiveLivenessSessionRepository()
    manager = ActiveGestureLivenessManager()

    def _repo():
        return repo

    def _start_uc():
        return StartActiveGestureLivenessUseCase(manager=manager, session_repository=repo)

    def _frame_uc():
        return ProcessActiveGestureLivenessFrameUseCase(
            manager=manager, session_repository=repo
        )

    app.dependency_overrides[container.get_active_liveness_session_repository] = _repo
    app.dependency_overrides[
        container.get_start_active_gesture_liveness_use_case
    ] = _start_uc
    app.dependency_overrides[
        container.get_process_active_gesture_liveness_frame_use_case
    ] = _frame_uc
    yield
    app.dependency_overrides.clear()
    container.clear_cache()


class TestShapeTemplatesEndpoint:
    def test_returns_four_templates_with_etag(self, client, enabled_gesture_backend):
        r = client.get("/api/v1/liveness/active/gesture/shape-templates")
        assert r.status_code == 200
        etag = r.headers.get("etag")
        assert etag and etag.startswith('W/"mtime-')
        data = r.json()
        keys = {t["key"] for t in data["templates"]}
        assert keys == {"circle", "square", "triangle", "s_curve"}

    def test_304_on_etag_match(self, client, enabled_gesture_backend):
        r = client.get("/api/v1/liveness/active/gesture/shape-templates")
        etag = r.headers["etag"]
        r2 = client.get(
            "/api/v1/liveness/active/gesture/shape-templates",
            headers={"If-None-Match": etag},
        )
        assert r2.status_code == 304


class TestSessionFlow:
    def test_start_returns_session_id_and_challenges(self, client, enabled_gesture_backend):
        r = client.post(
            "/api/v1/liveness/active/gesture/start",
            json={
                "num_challenges": 2,
                "required_gesture_challenges": ["hold_position", "finger_tap"],
                "challenge_timeout": 10.0,
                "session_timeout_seconds": 60.0,
                "randomize": False,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"]
        assert body["challenges_total"] == 2

    def test_full_session_hold_plus_tap_completes(self, client, enabled_gesture_backend):
        start = client.post(
            "/api/v1/liveness/active/gesture/start",
            json={
                "num_challenges": 2,
                "required_gesture_challenges": ["hold_position", "finger_tap"],
                "challenge_timeout": 30.0,
                "session_timeout_seconds": 120.0,
                "randomize": False,
            },
        ).json()
        session_id = start["session_id"]
        hand = _open_hand()
        # First challenge: HOLD_POSITION needs >=15 same-frame samples.
        for i in range(20):
            client.post(
                "/api/v1/liveness/active/gesture/frame",
                json={
                    "session_id": session_id,
                    "payload": {
                        "frame_time_ms": i * 33,
                        "landmarks_right": hand,
                        "landmarks_left": None,
                        "tremor_variance": 0.01,
                        "brightness_std": 0.5,
                    },
                },
            )
        # Second challenge: FINGER_TAP (index + middle tips close).
        tap_hand = _open_hand()
        tap_hand[8] = {"x": 0.498, "y": 0.36, "z": 0.0}
        tap_hand[12] = {"x": 0.500, "y": 0.36, "z": 0.0}
        final = None
        for i in range(5):
            r = client.post(
                "/api/v1/liveness/active/gesture/frame",
                json={
                    "session_id": session_id,
                    "payload": {
                        "frame_time_ms": 1000 + i * 33,
                        "landmarks_right": tap_hand,
                        "landmarks_left": None,
                        "tremor_variance": 0.01,
                        "brightness_std": 0.5,
                    },
                },
            )
            assert r.status_code == 200, r.text
            final = r.json()
            if final.get("session_complete"):
                break
        assert final is not None
        assert final["session_complete"] is True
        assert final["session_passed"] is True

    def test_404_on_unknown_session(self, client, enabled_gesture_backend):
        r = client.post(
            "/api/v1/liveness/active/gesture/frame",
            json={
                "session_id": "does-not-exist",
                "payload": {
                    "frame_time_ms": 0,
                    "landmarks_right": _open_hand(),
                    "landmarks_left": None,
                    "tremor_variance": 0.01,
                    "brightness_std": 0.5,
                },
            },
        )
        assert r.status_code == 404

    def test_410_gone_for_expired_session(self, client, enabled_gesture_backend):
        """P6.9 #7: expired sessions must surface as HTTP 410, not 404 or 500.

        Forces expiry by setting expires_at into the past, then submits a
        frame to the gesture endpoint. The 410 path is wired in
        app/api/routes/liveness.py via GestureSessionExpiredError.
        """

        start = client.post(
            "/api/v1/liveness/active/gesture/start",
            json={
                "num_challenges": 1,
                "required_gesture_challenges": ["hold_position"],
                "challenge_timeout": 10.0,
                "session_timeout_seconds": 60.0,
                "randomize": False,
            },
        ).json()
        session_id = start["session_id"]

        # Reach into the in-memory repo to expire this session deterministically.
        from app.core import container

        repo = container.get_active_liveness_session_repository()
        # The repo's internal store keys vary; iterate and force-mutate.
        # InMemoryActiveLivenessSessionRepository exposes ._sessions; we use
        # its public mutate() to keep the test honest.
        async def _expire(session):
            session.expires_at = 0.0  # epoch -> always in the past
            return session

        import asyncio

        asyncio.get_event_loop().run_until_complete(repo.mutate(session_id, _expire))

        r = client.post(
            "/api/v1/liveness/active/gesture/frame",
            json={
                "session_id": session_id,
                "payload": {
                    "frame_time_ms": 0,
                    "landmarks_right": _open_hand(),
                    "landmarks_left": None,
                    "tremor_variance": 0.01,
                    "brightness_std": 0.5,
                },
            },
        )
        assert r.status_code == 410, r.text

    def test_rejects_zero_tremor(self, client, enabled_gesture_backend):
        start = client.post(
            "/api/v1/liveness/active/gesture/start",
            json={
                "num_challenges": 1,
                "required_gesture_challenges": ["finger_tap"],
                "randomize": False,
            },
        ).json()
        session_id = start["session_id"]
        tap_hand = _open_hand()
        tap_hand[8] = {"x": 0.498, "y": 0.36, "z": 0.0}
        tap_hand[12] = {"x": 0.500, "y": 0.36, "z": 0.0}
        r = client.post(
            "/api/v1/liveness/active/gesture/frame",
            json={
                "session_id": session_id,
                "payload": {
                    "frame_time_ms": 0,
                    "landmarks_right": tap_hand,
                    "landmarks_left": None,
                    "tremor_variance": 1e-7,  # spoof-static
                    "brightness_std": 0.5,
                },
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["detection"] is not None
        assert body["detection"]["detected"] is False
        assert body["detection"]["details"].get("anti_spoof_rejected") is True
