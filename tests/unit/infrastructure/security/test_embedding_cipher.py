"""Unit tests for :class:`EmbeddingCipher` (P1.3).

Covers:
  * round-trip identity for typical 128/256/512-dim vectors
  * tamper detection (single bit flip → integrity error)
  * fail-fast when key env var is missing
  * dtype coercion (float64 input → float32 round-trip)
"""

from __future__ import annotations

import numpy as np
import pytest
from cryptography.fernet import Fernet

from app.infrastructure.security.embedding_cipher import EmbeddingCipher, _KEY_ENV


@pytest.fixture
def cipher() -> EmbeddingCipher:
    return EmbeddingCipher(key=Fernet.generate_key())


@pytest.mark.parametrize("dim", [128, 256, 512])
def test_round_trip_preserves_vector(cipher: EmbeddingCipher, dim: int) -> None:
    rng = np.random.default_rng(seed=1234)
    vec = rng.standard_normal(dim).astype(np.float32)

    blob = cipher.encrypt_vector(vec)
    out = cipher.decrypt_vector(blob)

    assert out.dtype == np.float32
    assert out.shape == vec.shape
    assert np.array_equal(out, vec)


def test_round_trip_coerces_float64_to_float32(cipher: EmbeddingCipher) -> None:
    vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    out = cipher.decrypt_vector(cipher.encrypt_vector(vec))
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, vec.astype(np.float32))


def test_tampered_ciphertext_raises(cipher: EmbeddingCipher) -> None:
    vec = np.arange(64, dtype=np.float32)
    blob = bytearray(cipher.encrypt_vector(vec))
    # Flip a byte in the middle of the body (after the Fernet version+ts header).
    flip_index = len(blob) // 2
    blob[flip_index] ^= 0xFF

    with pytest.raises(RuntimeError, match="integrity"):
        cipher.decrypt_vector(bytes(blob))


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match=_KEY_ENV):
        EmbeddingCipher()


def test_from_env_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(_KEY_ENV, key)
    c = EmbeddingCipher.from_env()
    vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert np.array_equal(c.decrypt_vector(c.encrypt_vector(vec)), vec)


def test_rejects_multi_dim_vector(cipher: EmbeddingCipher) -> None:
    bad = np.zeros((2, 3), dtype=np.float32)
    with pytest.raises(ValueError, match="1-D"):
        cipher.encrypt_vector(bad)


def test_decrypt_with_wrong_key_raises() -> None:
    a = EmbeddingCipher(key=Fernet.generate_key())
    b = EmbeddingCipher(key=Fernet.generate_key())
    vec = np.ones(8, dtype=np.float32)
    blob = a.encrypt_vector(vec)
    with pytest.raises(RuntimeError, match="integrity"):
        b.decrypt_vector(blob)
