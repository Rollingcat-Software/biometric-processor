"""Integration tests for ANTISPOOF_DEVICE_RISK_ENABLED on /verify (PR 4/5)."""

from __future__ import annotations

import io
import sys
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest

# Mock DeepFace before any imports that depend on it
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
    """Bundled mocks: verify use-case, liveness, file storage, observation repo.

    File storage's ``save_temp`` returns a path that actually exists on
    disk (a small JPEG) so the route's ``validate_image_file`` magic-byte
    check passes without us having to stub it.
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


def test_verify_omits_device_spoof_risk_when_flag_off(
    client: TestClient, mocks, test_image_file
) -> None:
    """When ANTISPOOF_DEVICE_RISK_ENABLED=False (default), the field is null."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    with patch.object(
        verify_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", False
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


def test_verify_attaches_device_spoof_risk_when_flag_on(
    client: TestClient, mocks, test_image_file
) -> None:
    """When ANTISPOOF_DEVICE_RISK_ENABLED=True, the field is a dict."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    fake_assessment = {
        "moire_risk": 0.12,
        "reflection_risk": 0.05,
        "flicker_risk": 0.0,
        "flash_response_score": 0.0,
        "flash_response_strength": 0.0,
        "flash_response_consistency": 0.0,
        "flash_replay_risk": 0.0,
        "hole_cutout_risk": 0.0,
        "focal_blur_anomaly_risk": 0.0,
        "cutout_spoof_support": 0.0,
        "screen_frame_risk": 0.0,
        "device_replay_risk": 0.04,
    }

    with patch.object(
        verify_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", True
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
    """If the evaluator throws, verification still succeeds with null risk."""
    verify_uc, liveness_uc, storage, observation_repo = mocks
    _wire_overrides(verify_uc, liveness_uc, storage, observation_repo)

    with patch.object(
        verify_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", True
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
    # The helper swallows the exception and returns None.
    assert body["device_spoof_risk"] is None
