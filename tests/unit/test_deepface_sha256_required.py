"""Tests for the DEEPFACE_SHA256_REQUIRED fail-fast behavior (Bug 5, 2026-05-12).

Previously, an empty ``DEEPFACE_FACENET512_SHA256`` only logged a WARNING
and continued loading the model. A silent weight rotation under
``~/.deepface/weights/`` could change embeddings without anyone noticing.

The new behavior:
  * ``DEEPFACE_SHA256_REQUIRED=true`` (default) AND
    ``ENVIRONMENT=production`` AND empty pin → RuntimeError at model-load.
  * Any other combination keeps the old warn-and-skip behavior so dev
    flows don't break.

We don't load the actual ~400MB DeepFace weights here — we just exercise
the integrity-check function directly with a tmp weight file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Mock the heavy ML deps before importing the extractor module under test.
# `deepface_extractor.py` does `from deepface import DeepFace` at module
# load, which pulls TensorFlow on dev hosts that don't have it. The
# integrity-check function itself only uses hashlib + pathlib — no TF.
#
# IMPORTANT: we do NOT mock `tensorflow` as a whole — that pollutes other
# tests in the same pytest session (notably the integration tests that
# import `app.main` which calls `gpu.configure_gpu()` and iterates over
# `tf.config.list_physical_devices('GPU')`). Mocking only `deepface`
# and `tf_keras` is enough because they're the deps that
# deepface_extractor.py's top-level import chain pulls in.
sys.modules.setdefault("tf_keras", Mock())
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())


@pytest.fixture
def fake_weight_file(tmp_path):
    """Create a small fake weight file so the integrity check has something
    to digest. The actual hash doesn't matter for the missing-pin tests."""
    weight = tmp_path / "facenet512_weights.h5"
    weight.write_bytes(b"fake-weight-content-for-integrity-testing-12345")
    return weight


def _patch_settings(**kwargs):
    """Patch attributes on the deepface_extractor module's `settings` import.

    The function imports `settings` lazily via `from app.core.config import settings`
    inside `_verify_model_integrity`, so we need to patch the actual module
    attribute used at call time.
    """
    import app.core.config as cfg_module
    return patch.multiple(cfg_module.settings, **kwargs)


def test_missing_pin_raises_in_prod_when_required(fake_weight_file):
    """Empty pin + prod env + required flag → RuntimeError."""
    from app.infrastructure.ml.extractors.deepface_extractor import (
        _verify_model_integrity,
    )

    with patch(
        "app.infrastructure.ml.extractors.deepface_extractor._resolve_weight_path",
        return_value=fake_weight_file,
    ), _patch_settings(
        DEEPFACE_FACENET512_SHA256="",
        DEEPFACE_SHA256_REQUIRED=True,
        ENVIRONMENT="production",
    ):
        with pytest.raises(RuntimeError) as exc_info:
            _verify_model_integrity("Facenet512")
        assert "integrity pin missing" in str(exc_info.value).lower()


def test_missing_pin_warns_in_dev(fake_weight_file, caplog):
    """Empty pin + dev env → log warning, no raise."""
    import logging

    from app.infrastructure.ml.extractors.deepface_extractor import (
        _verify_model_integrity,
    )

    with patch(
        "app.infrastructure.ml.extractors.deepface_extractor._resolve_weight_path",
        return_value=fake_weight_file,
    ), _patch_settings(
        DEEPFACE_FACENET512_SHA256="",
        DEEPFACE_SHA256_REQUIRED=True,
        ENVIRONMENT="development",
    ), caplog.at_level(logging.WARNING):
        # Must not raise.
        _verify_model_integrity("Facenet512")

    assert any(
        "skipped" in r.message.lower() and "no pinned hash" in r.message.lower()
        for r in caplog.records
    )


def test_missing_pin_warns_when_required_false_in_prod(fake_weight_file, caplog):
    """Opt-out flag must let prod boot with an empty pin (first-deploy scenario)."""
    import logging

    from app.infrastructure.ml.extractors.deepface_extractor import (
        _verify_model_integrity,
    )

    with patch(
        "app.infrastructure.ml.extractors.deepface_extractor._resolve_weight_path",
        return_value=fake_weight_file,
    ), _patch_settings(
        DEEPFACE_FACENET512_SHA256="",
        DEEPFACE_SHA256_REQUIRED=False,
        ENVIRONMENT="production",
    ), caplog.at_level(logging.WARNING):
        _verify_model_integrity("Facenet512")

    assert any(
        "skipped" in r.message.lower() for r in caplog.records
    )


def test_correct_pin_passes(fake_weight_file):
    """Pinned + correct hash → returns silently (success path)."""
    import hashlib

    from app.infrastructure.ml.extractors.deepface_extractor import (
        _verify_model_integrity,
    )

    expected = hashlib.sha256(fake_weight_file.read_bytes()).hexdigest()

    with patch(
        "app.infrastructure.ml.extractors.deepface_extractor._resolve_weight_path",
        return_value=fake_weight_file,
    ), _patch_settings(
        DEEPFACE_FACENET512_SHA256=expected,
        DEEPFACE_SHA256_REQUIRED=True,
        ENVIRONMENT="production",
    ):
        # Must not raise.
        _verify_model_integrity("Facenet512")


def test_wrong_pin_raises_regardless_of_env(fake_weight_file):
    """An explicit pin that doesn't match the file MUST raise everywhere."""
    from app.infrastructure.ml.extractors.deepface_extractor import (
        _verify_model_integrity,
    )

    with patch(
        "app.infrastructure.ml.extractors.deepface_extractor._resolve_weight_path",
        return_value=fake_weight_file,
    ), _patch_settings(
        DEEPFACE_FACENET512_SHA256="deadbeef" * 8,
        DEEPFACE_SHA256_REQUIRED=False,
        ENVIRONMENT="development",
    ):
        with pytest.raises(RuntimeError) as exc_info:
            _verify_model_integrity("Facenet512")
        assert "integrity check failed" in str(exc_info.value).lower()
