"""Tests for the CPU-safety startup validator on Settings.

Covers FINDINGS_2026-04-25 B1: refuse to boot with GPU-needing ML choices
on a CPU-only host (e.g. Hetzner CX43) unless the operator explicitly sets
ALLOW_HEAVY_ML=true.

Notes:
- Pydantic v2 wraps validator errors in ``ValidationError``. The original
  ``ValueError`` we raise is preserved as the underlying cause / message,
  so we accept either when asserting "raises".
- ``Facenet512`` is the SOFT-tier recognition model: prod currently runs
  it on CPU, so it must warn-log but NOT crash boot.
"""

import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _make(**overrides) -> Settings:
    """Build a Settings instance, ignoring any ambient .env file.

    We pass overrides directly (kwargs take priority over env), and we also
    explicitly clear _env_file so a developer's .env can't accidentally
    flip the test's expected outcome.
    """
    return Settings(_env_file=None, **overrides)


class TestConfigValidatorCpuSafety:
    """Startup validator: GPU-needing ML choices on CPU box."""

    def test_default_config_loads_cleanly(self):
        """Default config (opencv + Facenet) must load without raising."""
        s = _make()
        assert s.FACE_DETECTION_BACKEND == "opencv"
        assert s.FACE_RECOGNITION_MODEL == "Facenet"
        assert s.ALLOW_HEAVY_ML is False

    def test_retinaface_without_allow_heavy_ml_raises(self):
        """Heavy detection backend must fail fast on a CPU box."""
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            _make(FACE_DETECTION_BACKEND="retinaface")
        msg = str(exc_info.value)
        assert "FACE_DETECTION_BACKEND" in msg
        assert "ALLOW_HEAVY_ML" in msg

    @pytest.mark.parametrize("backend", [
        "yolov8", "yolov11n", "yolov11s", "yolov12n",
    ])
    def test_yolo_backends_raise(self, backend):
        """All YOLO detector variants are GPU-only by default."""
        with pytest.raises((ValidationError, ValueError)):
            _make(FACE_DETECTION_BACKEND=backend)

    @pytest.mark.parametrize("model", ["ArcFace", "VGG-Face", "GhostFaceNet"])
    def test_heavy_recognition_models_raise(self, model):
        """ArcFace / VGG-Face / GhostFaceNet must hard-fail on CPU."""
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            _make(FACE_RECOGNITION_MODEL=model)
        msg = str(exc_info.value)
        assert "FACE_RECOGNITION_MODEL" in msg

    def test_allow_heavy_ml_unblocks_retinaface(self):
        """Operator opt-in must permit heavy backends."""
        s = _make(FACE_DETECTION_BACKEND="retinaface", ALLOW_HEAVY_ML=True)
        assert s.FACE_DETECTION_BACKEND == "retinaface"
        assert s.ALLOW_HEAVY_ML is True

    def test_allow_heavy_ml_unblocks_arcface(self):
        """Operator opt-in must permit heavy recognition models."""
        s = _make(FACE_RECOGNITION_MODEL="ArcFace", ALLOW_HEAVY_ML=True)
        assert s.FACE_RECOGNITION_MODEL == "ArcFace"

    def test_facenet512_warns_but_does_not_crash(self, caplog):
        """SOFT tier: Facenet512 boots (prod uses it) but emits a WARN."""
        with caplog.at_level(logging.WARNING, logger="app.core.config"):
            s = _make(FACE_RECOGNITION_MODEL="Facenet512")
        assert s.FACE_RECOGNITION_MODEL == "Facenet512"
        assert any(
            "Facenet512" in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        ), f"expected a WARNING about Facenet512, got: {caplog.records!r}"

    def test_prod_current_config_does_not_crash(self):
        """Smoke: prod compose hardcodes Facenet512 + opencv. Must boot."""
        s = _make(
            FACE_DETECTION_BACKEND="opencv",
            FACE_RECOGNITION_MODEL="Facenet512",
        )
        assert s.FACE_DETECTION_BACKEND == "opencv"
        assert s.FACE_RECOGNITION_MODEL == "Facenet512"

    def test_facenet512_with_allow_heavy_ml_no_warning(self, caplog):
        """When operator opted in, no warning is emitted."""
        with caplog.at_level(logging.WARNING, logger="app.core.config"):
            s = _make(FACE_RECOGNITION_MODEL="Facenet512", ALLOW_HEAVY_ML=True)
        assert s.FACE_RECOGNITION_MODEL == "Facenet512"
        # no warning expected on opt-in path
        assert not any(
            "Facenet512" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )
