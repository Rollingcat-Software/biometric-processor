"""Tests for the shared MediaPipe FaceLandmarker (Tasks API) loader.

Added 2026-05-12 alongside the mp.solutions → mp.tasks.vision port. The
loader is the single integration seam between the codebase and the new
MediaPipe API, so these tests focus on path/SHA resolution semantics rather
than on actual landmark detection (which requires a real model file).
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Import under test
from app.infrastructure.ml.landmarks import face_landmarker_loader


class TestResolveFaceLandmarkerModelPath:
    """resolve_face_landmarker_model_path resolution order semantics."""

    def test_env_override_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = tmp_path / "custom.task"
        custom.write_bytes(b"stub")
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_PATH", str(custom))
        assert face_landmarker_loader.resolve_face_landmarker_model_path() == custom

    def test_env_pointing_to_missing_file_falls_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # env var points at a non-existent file. The loader should NOT return
        # that path. It should fall through to the next candidate(s); when
        # none exist it returns None.
        missing = tmp_path / "does_not_exist.task"
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_PATH", str(missing))
        # Stub the repo-relative default to also be missing.
        with mock.patch.object(
            face_landmarker_loader, "_DEFAULT_MODEL_PATH", tmp_path / "also_missing.task"
        ):
            # And cwd-relative path also missing — make cwd a tmp dir.
            monkeypatch.chdir(tmp_path)
            assert face_landmarker_loader.resolve_face_landmarker_model_path() is None

    def test_returns_none_when_nothing_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FACE_LANDMARKER_MODEL_PATH", raising=False)
        with mock.patch.object(
            face_landmarker_loader, "_DEFAULT_MODEL_PATH", tmp_path / "nope.task"
        ):
            monkeypatch.chdir(tmp_path)
            assert face_landmarker_loader.resolve_face_landmarker_model_path() is None


class TestVerifyModelSha256:
    """Integrity check skip / match / mismatch behaviour."""

    def test_skip_when_env_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FACE_LANDMARKER_MODEL_SHA256", raising=False)
        f = tmp_path / "x.task"
        f.write_bytes(b"any")
        assert face_landmarker_loader.verify_model_sha256(f) is True

    def test_match(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "x.task"
        f.write_bytes(b"hello world")
        digest = hashlib.sha256(b"hello world").hexdigest()
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_SHA256", digest)
        assert face_landmarker_loader.verify_model_sha256(f) is True

    def test_match_case_insensitive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "x.task"
        f.write_bytes(b"hello world")
        digest = hashlib.sha256(b"hello world").hexdigest().upper()
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_SHA256", digest)
        assert face_landmarker_loader.verify_model_sha256(f) is True

    def test_mismatch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "x.task"
        f.write_bytes(b"hello world")
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_SHA256", "deadbeef" * 8)
        assert face_landmarker_loader.verify_model_sha256(f) is False


class TestCreateFaceLandmarker:
    """create_face_landmarker fail-soft behaviour when assets/imports are absent."""

    def test_returns_none_when_model_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FACE_LANDMARKER_MODEL_PATH", raising=False)
        with mock.patch.object(
            face_landmarker_loader, "_DEFAULT_MODEL_PATH", tmp_path / "nope.task"
        ):
            monkeypatch.chdir(tmp_path)
            assert face_landmarker_loader.create_face_landmarker() is None

    def test_returns_none_when_sha256_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "fake.task"
        f.write_bytes(b"not-a-real-model")
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_PATH", str(f))
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_SHA256", "deadbeef" * 8)
        assert face_landmarker_loader.create_face_landmarker() is None

    def test_returns_none_when_mediapipe_import_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "fake.task"
        f.write_bytes(b"stub")
        monkeypatch.setenv("FACE_LANDMARKER_MODEL_PATH", str(f))
        monkeypatch.delenv("FACE_LANDMARKER_MODEL_SHA256", raising=False)

        # Simulate Tasks API import failure. The loader catches ImportError
        # and returns None — verifying we never crash a request just because
        # mediapipe is uninstallable on a particular host.
        with mock.patch.dict(
            sys.modules,
            {
                "mediapipe.tasks": None,
                "mediapipe.tasks.python": None,
            },
        ):
            assert face_landmarker_loader.create_face_landmarker() is None


class TestToMpImage:
    """to_mp_image helper wraps RGB arrays in mp.Image."""

    def test_returns_mp_image_with_srgb_format(self) -> None:
        pytest.importorskip("mediapipe")
        import numpy as np

        # mp.Image instantiation pulls in libGLESv2.so.2 via the C bindings.
        # CI images that strip GL/EGL libs cannot exercise the constructor;
        # skip rather than fail-spuriously. The runtime container does have
        # libgl1 installed (see Dockerfile) so this test passes there.
        try:
            wrapped = face_landmarker_loader.to_mp_image(
                np.zeros((10, 10, 3), dtype=np.uint8)
            )
        except OSError as exc:
            pytest.skip(f"mediapipe native libs unavailable in this env: {exc}")
        assert wrapped is not None
        # Defensive: width/height are stable public attributes since 0.10.x.
        assert wrapped.width == 10
        assert wrapped.height == 10
