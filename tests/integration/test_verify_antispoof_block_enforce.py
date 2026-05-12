"""Integration tests for ANTISPOOF_BLOCK_ENFORCE + ANTISPOOF_EAR_VETO_ENABLED.

Bugs fixed 2026-05-12:
  * Bug 1: AntispoofPipelineAssembler `recommended_action="block"` was
    advisory — the route attached it to the response but still returned
    200/verified=True. We now return 403 with a structured body when
    enforce is on.
  * Bug 2: blink-cache/EAR work from spoof-detector was unreachable from
    /verify. We now wire `compute_ear` into a single-frame check and
    veto when both eyes are closed.

Per the existing test_verify_antispoof_wiring.py convention this file uses
a module-scoped TestClient to avoid the anyio-portal closed-loop issue when
the route's lru-cached deps are recreated mid-suite.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest

# Mock DeepFace before any imports that depend on it (same pattern as
# test_verify_antispoof_wiring.py). Resemblyzer is required by main.py's
# lifespan via SpeakerEmbedder; the dev host doesn't have it installed
# (it's a CPU-heavy optional dep), so mock it too so the TestClient
# lifespan succeeds. This is the "baseline rot" pattern documented in
# bio main — 79 pre-existing failing tests share the same root cause.
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())
sys.modules.setdefault("resemblyzer", Mock(VoiceEncoder=Mock()))

from fastapi.testclient import TestClient

from app.api.routes import verification as verify_route
from app.core.container import (
    get_check_liveness_use_case,
    get_client_embedding_observation_repository,
    get_file_storage,
    get_verify_face_use_case,
)
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.verification_result import VerificationResult
from app.main import app


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


@pytest.fixture
def mocks(tmp_path):
    """Wire all upstream deps with fast, deterministic AsyncMocks."""
    img = np.full((100, 100, 3), 80, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    image_path = tmp_path / "saved.jpg"
    image_path.write_bytes(buf.tobytes())

    verify_uc = Mock()
    verify_uc.execute = AsyncMock(
        return_value=VerificationResult(
            verified=True, confidence=0.87, distance=0.13, threshold=0.6,
        )
    )

    liveness_uc = Mock()
    liveness_uc.execute = AsyncMock(
        return_value=LivenessResult(
            is_live=True, score=92.0, challenge="none",
            challenge_completed=True, confidence=0.91,
        )
    )

    storage = Mock()
    storage.save_temp = AsyncMock(return_value=str(image_path))
    storage.cleanup = AsyncMock()

    observation_repo = Mock()
    observation_repo.record = AsyncMock()

    return verify_uc, liveness_uc, storage, observation_repo


def _wire(verify_uc, liveness_uc, storage, observation_repo) -> None:
    app.dependency_overrides[get_verify_face_use_case] = lambda: verify_uc
    app.dependency_overrides[get_check_liveness_use_case] = lambda: liveness_uc
    app.dependency_overrides[get_file_storage] = lambda: storage
    app.dependency_overrides[get_client_embedding_observation_repository] = (
        lambda: observation_repo
    )


# ---------------------------------------------------------------------------
# Bug 1: enforce assembler recommended_action="block"
# ---------------------------------------------------------------------------


def test_block_verdict_triggers_403_when_enforce_on(
    client: TestClient, mocks, test_image_file
) -> None:
    """recommended_action='block' + enforce=True → HTTP 403."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    fake_block_result = {
        "face_usability_block": True,
        "face_usability_reason": "occluded",
        "device_replay_risk": 0.05,
        "device_signals": {"moire_risk": 0.0},
        "hybrid_fusion_is_spoof": None,
        "hybrid_fusion_score": None,
        "hybrid_fusion_reasoning": None,
        "recommended_action": "block",
        "layers_evaluated": ["face_usability"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe",
        return_value=fake_block_result,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_block"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail") or body
    assert detail.get("error_code") == "ANTISPOOF_BLOCKED"
    assert detail.get("reason") == "FACE_UNUSABLE"
    assert detail.get("antispoof_pipeline") == fake_block_result


def test_block_verdict_passes_when_enforce_off(
    client: TestClient, mocks, test_image_file
) -> None:
    """recommended_action='block' + enforce=False → 200 + verdict attached."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    fake_block_result = {
        "face_usability_block": False,
        "face_usability_reason": None,
        "device_replay_risk": 0.85,
        "device_signals": {"moire_risk": 0.7},
        "hybrid_fusion_is_spoof": True,
        "hybrid_fusion_score": 0.92,
        "hybrid_fusion_reasoning": "spoof detected via fusion",
        "recommended_action": "block",
        "layers_evaluated": ["device_spoof_risk", "hybrid_fusion"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe",
        return_value=fake_block_result,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_observe"},
            files={"file": test_image_file},
        )

    # Enforce off — verification still returns 200 with the verdict attached.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["antispoof_pipeline"] == fake_block_result


def test_allow_verdict_passes_with_enforce_on(
    client: TestClient, mocks, test_image_file
) -> None:
    """recommended_action='allow' must never trigger a block."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    fake_allow_result = {
        "face_usability_block": False,
        "face_usability_reason": None,
        "device_replay_risk": 0.05,
        "device_signals": {"moire_risk": 0.01},
        "hybrid_fusion_is_spoof": False,
        "hybrid_fusion_score": 0.18,
        "hybrid_fusion_reasoning": "LIVE verified",
        "recommended_action": "allow",
        "layers_evaluated": ["device_spoof_risk", "hybrid_fusion"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe",
        return_value=fake_allow_result,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_allow"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True


def test_review_verdict_passes_with_enforce_on(
    client: TestClient, mocks, test_image_file
) -> None:
    """recommended_action='review' must NOT cause a block (review != block)."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    fake_review_result = {
        "face_usability_block": False,
        "face_usability_reason": None,
        "device_replay_risk": 0.72,
        "device_signals": {"moire_risk": 0.3},
        "hybrid_fusion_is_spoof": False,
        "hybrid_fusion_score": 0.5,
        "hybrid_fusion_reasoning": "borderline",
        "recommended_action": "review",
        "layers_evaluated": ["device_spoof_risk", "hybrid_fusion"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe",
        return_value=fake_review_result,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_review"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["antispoof_pipeline"] == fake_review_result


# ---------------------------------------------------------------------------
# Bug 2: EAR closed-eye veto
# ---------------------------------------------------------------------------


def test_ear_closed_eyes_triggers_403_when_enforce_on(
    client: TestClient, mocks, test_image_file
) -> None:
    """eyes_closed=True from EAR check vetoes the request alongside assembler."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    fake_ear_result = {
        "eyes_closed": True,
        "left_ear": 0.12,
        "right_ear": 0.10,
        "avg_ear": 0.11,
        "threshold": 0.18,
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", return_value=fake_ear_result,
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=None,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_ear"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 403, resp.text
    detail = resp.json().get("detail") or {}
    assert detail.get("error_code") == "ANTISPOOF_BLOCKED"
    assert detail.get("reason") == "EYES_CLOSED"
    assert detail.get("ear_liveness") == fake_ear_result


def test_ear_open_eyes_passes(
    client: TestClient, mocks, test_image_file
) -> None:
    """eyes_closed=False → response includes ear_liveness but verifies OK."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    fake_ear_result = {
        "eyes_closed": False,
        "left_ear": 0.28,
        "right_ear": 0.30,
        "avg_ear": 0.29,
        "threshold": 0.18,
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", return_value=fake_ear_result,
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=None,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_ear_open"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["ear_liveness"] == fake_ear_result


def test_ear_helper_is_called_when_flag_on(
    client: TestClient, mocks, test_image_file
) -> None:
    """Regression guard for Bug 2: the EAR helper must actually be invoked
    from /verify when the flag is on. Asserts the path is reached at least
    once (previously zero — the wiring was missing).
    """
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    ear_mock = Mock(return_value=None)

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_ear_liveness_safe", ear_mock,
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=None,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_ear_called"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    assert ear_mock.call_count == 1, (
        "EAR helper must be invoked from /verify (Bug 2 regression guard); "
        f"got {ear_mock.call_count} calls."
    )


def test_ear_helper_returns_none_when_flag_off(
    client: TestClient, mocks, test_image_file
) -> None:
    """When ANTISPOOF_EAR_VETO_ENABLED=False, the helper must short-circuit
    and return None — the route must not even attempt MediaPipe import.
    """
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire(verify_uc, liveness_uc, storage, observation_repo)

    with patch.object(
        verify_route.settings, "ANTISPOOF_BLOCK_ENFORCE", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_EAR_VETO_ENABLED", False
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe", return_value=None,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_ear_off"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["ear_liveness"] is None
