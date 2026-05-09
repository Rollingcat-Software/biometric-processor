"""Integration tests for the spoof-detector wiring on /verify.

Replaces (and supersedes) the older `test_verify_device_spoof_risk.py`
that lived on the closed PR #85. The wiring shape is the same — the only
difference is that the algorithms now come from the standalone
`spoof-detector` package (v0.2.0) instead of a sibling module.

These are integration tests at the route level. Per the architecture
decision 2026-05-09: the algorithms themselves are unit-tested in the
`spoof-detector` repo (46 tests there); this file only verifies the
wiring (flags off / on / evaluator throws / assembler enabled).
"""

from __future__ import annotations

import io
import sys
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest

# Mock DeepFace before any imports that depend on it.
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())

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


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_image_file():
    img = np.full((100, 100, 3), 80, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return ("test.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")


@pytest.fixture
def mocks(tmp_path):
    """Bundle: verify use-case, liveness, file storage, observation repo.

    File storage's ``save_temp`` returns a path that actually exists on
    disk (a small JPEG) so the route's ``validate_image_file`` magic-byte
    check passes.
    """
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


def _wire_overrides(verify_uc, liveness_uc, storage, observation_repo) -> None:
    app.dependency_overrides[get_verify_face_use_case] = lambda: verify_uc
    app.dependency_overrides[get_check_liveness_use_case] = lambda: liveness_uc
    app.dependency_overrides[get_file_storage] = lambda: storage
    app.dependency_overrides[get_client_embedding_observation_repository] = (
        lambda: observation_repo
    )


# ---------------------------------------------------------------------------
# Device-spoof risk (replaces PR #85)
# ---------------------------------------------------------------------------


def test_verify_omits_device_spoof_risk_when_flag_off(
    client: TestClient, mocks, test_image_file
) -> None:
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    with patch.object(
        verify_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_USABILITY_GATE_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_CUTOUT_ENABLED", False
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["device_spoof_risk"] is None
    assert body["antispoof_pipeline"] is None


def test_verify_attaches_device_spoof_risk_when_flag_on(
    client: TestClient, mocks, test_image_file
) -> None:
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    fake_assessment = {
        "moire_risk": 0.12,
        "reflection_risk": 0.05,
        "flicker_risk": 0.0,
        "flash_response_score": 0.0,
        "flash_replay_risk": 0.0,
        "hole_cutout_risk": 0.0,
        "screen_frame_risk": 0.0,
        "device_replay_risk": 0.04,
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_USABILITY_GATE_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_CUTOUT_ENABLED", False
    ), patch.object(
        verify_route, "_evaluate_device_spoof_risk_safe",
        return_value=fake_assessment,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["device_spoof_risk"] == fake_assessment


def test_verify_does_not_break_when_evaluator_raises(
    client: TestClient, mocks, test_image_file
) -> None:
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    with patch.object(
        verify_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", True
    ), patch.object(
        verify_route.settings, "ANTISPOOF_USABILITY_GATE_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_CUTOUT_ENABLED", False
    ), patch.object(
        verify_route, "_get_device_spoof_risk_evaluator",
        side_effect=RuntimeError("synthetic detector failure"),
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["device_spoof_risk"] is None


# ---------------------------------------------------------------------------
# Pipeline assembler (replaces PR #86)
# ---------------------------------------------------------------------------


def test_verify_omits_antispoof_pipeline_when_all_flags_off(
    client: TestClient, mocks, test_image_file
) -> None:
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    with patch.object(
        verify_route.settings, "ANTISPOOF_USABILITY_GATE_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", False
    ), patch.object(
        verify_route.settings, "ANTISPOOF_CUTOUT_ENABLED", False
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["antispoof_pipeline"] is None


def test_verify_attaches_antispoof_pipeline_when_assembler_enabled(
    client: TestClient, mocks, test_image_file
) -> None:
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    fake_pipeline_result = {
        "face_usability_block": False,
        "face_usability_reason": None,
        "device_replay_risk": 0.18,
        "device_signals": {"moire_risk": 0.12, "device_replay_risk": 0.18},
        "hybrid_fusion_is_spoof": False,
        "hybrid_fusion_score": 0.27,
        "hybrid_fusion_reasoning": "LIVE verified (score=0.27).",
        "recommended_action": "allow",
        "layers_evaluated": ["device_spoof_risk", "hybrid_fusion"],
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", True
    ), patch.object(
        verify_route, "_evaluate_antispoof_pipeline_safe",
        return_value=fake_pipeline_result,
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["antispoof_pipeline"] == fake_pipeline_result


def test_antispoof_pipeline_safe_returns_none_when_dep_missing(
    client: TestClient, mocks, test_image_file
) -> None:
    """If the spoof_detector package isn't installed, the helper must
    fail soft and return None — verification still succeeds.
    """
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    # Force the assembler-init path to fail by making the dep missing.
    with patch.object(
        verify_route.settings, "ANTISPOOF_FUSION_ENABLED", True
    ), patch.dict(
        sys.modules,
        {
            "src": Mock(),
            "src.fusion": Mock(spec=[]),  # empty mock — `from src.fusion import HybridFusionEvaluator` will AttributeError
            "src.gates": Mock(spec=[]),
            "src.pipeline": Mock(spec=[]),
        },
        clear=False,
    ), patch.object(verify_route, "_antispoof_assembler", None), patch.object(
        verify_route, "_antispoof_assembler_init_failed", False
    ):
        resp = client.post(
            "/api/v1/verify",
            data={"user_id": "test_user_123"},
            files={"file": test_image_file},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["antispoof_pipeline"] is None
