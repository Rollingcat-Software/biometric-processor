"""Integration tests for the /liveness/flash-challenge route (PR 2/5)."""

from __future__ import annotations

import base64
import sys
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

# Mock DeepFace before any imports that depend on it
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.flash_challenge import router as flash_router


@pytest.fixture
def client_with_flag_on() -> TestClient:
    """Build a minimal FastAPI app that includes only the flash-challenge router.

    We don't import app.main because the global app object's router list
    depends on whether FLASH_CHALLENGE_ROUTE_ENABLED was true at import time;
    the route is gated behind that flag in main.py.
    """
    app = FastAPI()
    app.include_router(flash_router, prefix="/api/v1")
    return TestClient(app)


def _encode_solid_bgr(b: int, g: int, r: int, size: int = 32) -> str:
    """Encode a solid-colour BGR JPEG as base64."""
    frame = np.full((size, size, 3), (b, g, r), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


def test_start_returns_a_challenge(client_with_flag_on: TestClient) -> None:
    response = client_with_flag_on.post("/api/v1/liveness/flash-challenge/start")
    assert response.status_code == 200
    body = response.json()
    assert body["color"] in {"red", "green", "blue", "white", "yellow"}
    assert body["duration_ms"] == 150
    assert body["expected_response_window_ms"] == 500
    assert body["expires_at"] > body["issued_at"]
    assert body["baseline_required"] is True


def test_respond_happy_path_red(client_with_flag_on: TestClient) -> None:
    """A reddish frame within the response window passes for expected_color=red."""
    # JPEG encoding can drift colour slightly; use a strongly red frame.
    frame_b64 = _encode_solid_bgr(b=40, g=40, r=200)
    payload = {
        "expected_color": "red",
        "flash_timestamp": 1000.0,
        "frame_timestamp": 1000.20,
        "frame_base64": frame_b64,
        "baseline_bgr": [40.0, 40.0, 40.0],
    }
    response = client_with_flag_on.post(
        "/api/v1/liveness/flash-challenge/respond", json=payload
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is True
    assert body["color_shift"] is not None and body["color_shift"] > 0


def test_respond_rejects_timing_mismatch(client_with_flag_on: TestClient) -> None:
    """Frame captured before the minimum delay fails."""
    frame_b64 = _encode_solid_bgr(b=40, g=40, r=200)
    payload = {
        "expected_color": "red",
        "flash_timestamp": 1000.0,
        "frame_timestamp": 1000.001,  # 1 ms — below 50 ms minimum
        "frame_base64": frame_b64,
        "baseline_bgr": [40.0, 40.0, 40.0],
    }
    response = client_with_flag_on.post(
        "/api/v1/liveness/flash-challenge/respond", json=payload
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["reason"] == "timing_mismatch"


def test_respond_rejects_invalid_base64(client_with_flag_on: TestClient) -> None:
    payload = {
        "expected_color": "red",
        "flash_timestamp": 1000.0,
        "frame_timestamp": 1000.20,
        "frame_base64": "not!!base64!!",
        "baseline_bgr": [40.0, 40.0, 40.0],
    }
    response = client_with_flag_on.post(
        "/api/v1/liveness/flash-challenge/respond", json=payload
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_base64"


def test_respond_rejects_undecodable_frame(client_with_flag_on: TestClient) -> None:
    payload = {
        "expected_color": "red",
        "flash_timestamp": 1000.0,
        "frame_timestamp": 1000.20,
        # valid base64 but not an image
        "frame_base64": base64.b64encode(b"hello world").decode("ascii"),
        "baseline_bgr": [40.0, 40.0, 40.0],
    }
    response = client_with_flag_on.post(
        "/api/v1/liveness/flash-challenge/respond", json=payload
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "undecodable_frame"


def test_respond_rejects_unsupported_color(client_with_flag_on: TestClient) -> None:
    frame_b64 = _encode_solid_bgr(b=40, g=40, r=200)
    payload = {
        "expected_color": "magenta",
        "flash_timestamp": 1000.0,
        "frame_timestamp": 1000.20,
        "frame_base64": frame_b64,
    }
    response = client_with_flag_on.post(
        "/api/v1/liveness/flash-challenge/respond", json=payload
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported_color"


def test_respond_rejects_bad_baseline_length(client_with_flag_on: TestClient) -> None:
    frame_b64 = _encode_solid_bgr(b=40, g=40, r=200)
    payload = {
        "expected_color": "red",
        "flash_timestamp": 1000.0,
        "frame_timestamp": 1000.20,
        "frame_base64": frame_b64,
        "baseline_bgr": [40.0, 40.0],
    }
    response = client_with_flag_on.post(
        "/api/v1/liveness/flash-challenge/respond", json=payload
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "baseline_bgr_must_be_length_3"
