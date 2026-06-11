"""Integration tests for the enroll-time liveness + anti-spoof gate.

Closes the documented enroll/verify asymmetry (parent CLAUDE.md: "Faz 2'de
düzeltilecek"). The /enroll face path now runs the SAME passive liveness +
spoof-detector anti-spoof / EAR veto that /verify runs, BEFORE persisting the
embedding, gated behind ENROLL_LIVENESS_ENABLED (default ON).

Per the existing test_verify_antispoof_block_enforce.py convention this file
uses a module-scoped TestClient to avoid the anyio-portal closed-loop issue
when the route's lru-cached deps are recreated mid-suite. The enroll route
calls the anti-spoof helpers via the `verification` module, so we patch the
helpers on `verify_route` exactly as the verify tests do.
"""

from __future__ import annotations

import io
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest

# Mock heavy/optional deps before importing the app (same baseline-rot pattern
# documented in bio main and used by test_verify_antispoof_block_enforce.py).
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())
sys.modules.setdefault("resemblyzer", Mock(VoiceEncoder=Mock()))

from fastapi.testclient import TestClient

from app.api.routes import verification as verify_route
from app.core.container import (
    get_check_liveness_use_case,
    get_client_embedding_observation_repository,
    get_enroll_face_use_case,
    get_file_storage,
    get_idempotency_store,
)
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.liveness_result import LivenessResult
from app.main import app

# Module-level skip. `with TestClient(app)` runs the app startup lifespan, which
# pre-loads the full native ML stack (torch + uniface MiniFASNet ONNX). On the
# lightweight CI runner the drifted `>=` deps segfault during that load (the
# same native-drift crash tracked as P0-2b), taking down the whole
# `pytest tests/integration/` process (exit 139). Gate behind the full-stack
# flag so this skips on CI and runs inside the Docker ML stack (pinned deps).
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_FULL_STACK_INTEGRATION") != "true",
    reason="Loads the full ML stack via app lifespan (TestClient(app)); "
    "set RUN_FULL_STACK_INTEGRATION=true inside the Docker ML stack.",
)


@pytest.fixture(scope="module")
def _module_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(_module_client) -> TestClient:
    verify_route._antispoof_assembler = None
    verify_route._antispoof_assembler_init_failed = False
    verify_route._device_spoof_risk_evaluator = None
    verify_route._face_landmarker_for_ear = None
    verify_route._face_landmarker_for_ear_init_failed = False
    app.dependency_overrides.clear()

    yield _module_client

    app.dependency_overrides.clear()
    verify_route._antispoof_assembler = None
    verify_route._antispoof_assembler_init_failed = False
    verify_route._device_spoof_risk_evaluator = None
    verify_route._face_landmarker_for_ear = None
    verify_route._face_landmarker_for_ear_init_failed = False


@pytest.fixture
def test_image_file():
    img = np.full((100, 100, 3), 80, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return ("test.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")


def _make_live_liveness_uc():
    uc = Mock()
    uc.execute = AsyncMock(
        return_value=LivenessResult(
            is_live=True, score=92.0, challenge="none",
            challenge_completed=True, confidence=0.91,
        )
    )
    return uc


def _make_spoof_liveness_uc():
    uc = Mock()
    uc.execute = AsyncMock(
        return_value=LivenessResult(
            is_live=False, score=12.0, challenge="none",
            challenge_completed=True, confidence=0.20,
        )
    )
    return uc


@pytest.fixture
def mocks(tmp_path):
    """Wire all upstream enroll deps with fast, deterministic mocks."""
    img = np.full((100, 100, 3), 80, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    image_path = tmp_path / "saved.jpg"
    image_path.write_bytes(buf.tobytes())

    enroll_uc = Mock()
    enroll_uc.execute = AsyncMock(
        return_value=FaceEmbedding.create_new(
            user_id="test_user",
            vector=np.full(512, 0.1, dtype=np.float32),
            quality_score=85.0,
        )
    )

    liveness_uc = _make_live_liveness_uc()

    storage = Mock()
    storage.save_temp = AsyncMock(return_value=str(image_path))
    storage.cleanup = AsyncMock()

    idempotency_store = Mock()
    idempotency_store.get_response = AsyncMock(return_value=None)
    idempotency_store.store_response = AsyncMock()

    observation_repo = Mock()
    observation_repo.record = AsyncMock()

    return enroll_uc, liveness_uc, storage, idempotency_store, observation_repo


def _wire(enroll_uc, liveness_uc, storage, idempotency_store, observation_repo) -> None:
    app.dependency_overrides[get_enroll_face_use_case] = lambda: enroll_uc
    app.dependency_overrides[get_check_liveness_use_case] = lambda: liveness_uc
    app.dependency_overrides[get_file_storage] = lambda: storage
    app.dependency_overrides[get_idempotency_store] = lambda: idempotency_store
    app.dependency_overrides[get_client_embedding_observation_repository] = (
        lambda: observation_repo
    )


# ---------------------------------------------------------------------------
# Live frame passes + embedding is persisted
# ---------------------------------------------------------------------------


def test_enroll_passes_with_live_frame(client, mocks, test_image_file) -> None:
    """A live frame with no spoof veto enrolls successfully (200)."""
    enroll_uc, liveness_uc, storage, idem, obs = mocks
    _wire(enroll_uc, liveness_uc, storage, idem, obs)

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=None
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", return_value=None
    ):
        resp = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_live"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["liveness_score"] == 92.0
    # Embedding was persisted (use case executed).
    enroll_uc.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Spoof verdict (basic liveness) rejects + does NOT persist
# ---------------------------------------------------------------------------


def test_enroll_rejects_when_liveness_not_live(client, mocks, test_image_file) -> None:
    """is_live=False → 400 LIVENESS_FAILED and embedding is NOT persisted."""
    enroll_uc, _liveness_uc, storage, idem, obs = mocks
    spoof_liveness_uc = _make_spoof_liveness_uc()
    _wire(enroll_uc, spoof_liveness_uc, storage, idem, obs)

    with patch.object(verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True):
        resp = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_spoof"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 400, resp.text
    detail = resp.json().get("detail") or {}
    assert detail.get("error_code") == "LIVENESS_FAILED"
    # CRITICAL: spoof must NOT be persisted.
    enroll_uc.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# Anti-spoof pipeline "block" verdict rejects + does NOT persist
# ---------------------------------------------------------------------------


def test_enroll_rejects_on_antispoof_block(client, mocks, test_image_file) -> None:
    """recommended_action='block' + enforce=True → 403 ANTISPOOF_BLOCKED, no persist."""
    enroll_uc, liveness_uc, storage, idem, obs = mocks
    _wire(enroll_uc, liveness_uc, storage, idem, obs)

    fake_block = {
        "face_usability_block": True,
        "face_usability_reason": "occluded",
        "hybrid_fusion_is_spoof": None,
        "recommended_action": "block",
        "layers_evaluated": ["face_usability"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=fake_block
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", return_value=None
    ):
        resp = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_block"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 403, resp.text
    detail = resp.json().get("detail") or {}
    assert detail.get("error_code") == "ANTISPOOF_BLOCKED"
    assert detail.get("reason") == "FACE_UNUSABLE"
    assert detail.get("antispoof_pipeline") == fake_block
    # CRITICAL: spoof must NOT be persisted.
    enroll_uc.execute.assert_not_awaited()


def test_enroll_rejects_on_ear_closed_eyes(client, mocks, test_image_file) -> None:
    """EAR eyes_closed=True → 403 ANTISPOOF_BLOCKED (EYES_CLOSED), no persist."""
    enroll_uc, liveness_uc, storage, idem, obs = mocks
    _wire(enroll_uc, liveness_uc, storage, idem, obs)

    fake_ear = {
        "eyes_closed": True,
        "left_ear": 0.12,
        "right_ear": 0.10,
        "avg_ear": 0.11,
        "threshold": 0.18,
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=None
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", return_value=fake_ear
    ):
        resp = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_ear"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 403, resp.text
    detail = resp.json().get("detail") or {}
    assert detail.get("error_code") == "ANTISPOOF_BLOCKED"
    assert detail.get("reason") == "EYES_CLOSED"
    enroll_uc.execute.assert_not_awaited()


def test_enroll_antispoof_observe_mode_does_not_block(
    client, mocks, test_image_file
) -> None:
    """block verdict + ANTISPOOF_BLOCK_ENFORCE=False → 200, embedding persisted."""
    enroll_uc, liveness_uc, storage, idem, obs = mocks
    _wire(enroll_uc, liveness_uc, storage, idem, obs)

    fake_block = {
        "face_usability_block": False,
        "hybrid_fusion_is_spoof": True,
        "recommended_action": "block",
        "layers_evaluated": ["hybrid_fusion"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", False
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=fake_block
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", return_value=None
    ):
        resp = client.post(
            "/api/v1/enroll",
            data={"user_id": "test_user_observe"},
            files={"file": test_image_file},
        )

    # Observation mode: verdict suppressed, enrollment proceeds.
    assert resp.status_code == 200, resp.text
    enroll_uc.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# The flag disables the gate entirely
# ---------------------------------------------------------------------------


def test_enroll_gate_disabled_skips_liveness(client, mocks, test_image_file) -> None:
    """ENROLL_LIVENESS_ENABLED=False → liveness use case is never called,
    anti-spoof helpers are never called, enrollment proceeds (200) and
    liveness_score is None.
    """
    enroll_uc, _live_uc, storage, idem, obs = mocks
    # Use a spoof liveness UC to prove it is NOT consulted when the gate is off.
    spoof_liveness_uc = _make_spoof_liveness_uc()
    _wire(enroll_uc, spoof_liveness_uc, storage, idem, obs)

    antispoof_mock = Mock(return_value=None)
    ear_mock = Mock(return_value=None)

    with patch.object(
        verify_route.settings, "ENROLL_LIVENESS_ENABLED", False
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", antispoof_mock
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", ear_mock
    ):
        # The enroll route reads settings via its own module import; patch both
        # to be safe (same Settings singleton object instance).
        from app.api.routes import enrollment as enroll_route

        with patch.object(enroll_route.settings, "ENROLL_LIVENESS_ENABLED", False):
            resp = client.post(
                "/api/v1/enroll",
                data={"user_id": "test_user_gate_off"},
                files={"file": test_image_file},
            )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["liveness_score"] is None
    # Gate off: liveness UC not consulted, anti-spoof helpers not called.
    spoof_liveness_uc.execute.assert_not_awaited()
    assert antispoof_mock.call_count == 0
    assert ear_mock.call_count == 0
    enroll_uc.execute.assert_awaited_once()
