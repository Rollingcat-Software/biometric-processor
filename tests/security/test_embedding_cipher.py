"""Tests for ``app.security.embedding_cipher.EmbeddingCipher``.

Mirrors the Java ``TotpSecretCipherTest`` so both services fail in the
same ways for the same inputs:

* Round-trip plaintext → ciphertext → plaintext.
* Each encrypt emits a fresh IV (two ciphertexts of the same plaintext
  are bit-different and both decrypt correctly).
* Tampering with the ciphertext → generic "decryption failed".
* AAD mismatch → generic "decryption failed".
* Missing KEK → fail-fast at construction.
* Non-base64 KEK → fail-fast at construction.
* Wrong-length KEK (decoded bytes != 32) → fail-fast at construction.
"""

from __future__ import annotations

import base64
import os

import pytest

from app.security.embedding_cipher import (
    CIPHERTEXT_PREFIX,
    EmbeddingCipher,
)


def _fresh_kek_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


class TestEmbeddingCipherRoundTrip:
    def test_round_trip(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        plaintext = b"The quick brown fox jumps over the lazy dog"
        aad = b"face:tenant-a:user-42"

        ciphertext = cipher.encrypt(plaintext, aad)
        assert ciphertext.startswith(CIPHERTEXT_PREFIX)
        assert cipher.is_encrypted(ciphertext)

        recovered = cipher.decrypt(ciphertext, aad)
        assert recovered == plaintext

    def test_iv_uniqueness_across_encryptions(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        plaintext = b"same plaintext"
        aad = b"same aad"

        c1 = cipher.encrypt(plaintext, aad)
        c2 = cipher.encrypt(plaintext, aad)

        assert c1 != c2, "Two encryptions must produce distinct ciphertexts (IV reuse)"
        # Both must still decrypt correctly.
        assert cipher.decrypt(c1, aad) == plaintext
        assert cipher.decrypt(c2, aad) == plaintext

    def test_is_encrypted_accepts_any_type(self) -> None:
        assert EmbeddingCipher.is_encrypted(None) is False
        assert EmbeddingCipher.is_encrypted(123) is False
        assert EmbeddingCipher.is_encrypted("") is False
        assert EmbeddingCipher.is_encrypted("legacy-plaintext") is False
        assert EmbeddingCipher.is_encrypted(f"{CIPHERTEXT_PREFIX}abcd") is True


class TestEmbeddingCipherFailures:
    def test_tamper_triggers_generic_failure(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        plaintext = b"secret"
        aad = b"aad"

        ciphertext = cipher.encrypt(plaintext, aad)
        # Decode, flip one raw byte in the ciphertext region (after IV),
        # re-encode — guarantees auth-tag failure rather than base64 failure.
        body_b64 = ciphertext[len(CIPHERTEXT_PREFIX):]
        raw = bytearray(base64.b64decode(body_b64))
        # Flip a byte in the middle so we stay inside the ct+tag region.
        mid = len(raw) // 2
        raw[mid] ^= 0x01
        tampered = CIPHERTEXT_PREFIX + base64.b64encode(bytes(raw)).decode("ascii")

        with pytest.raises(ValueError) as excinfo:
            cipher.decrypt(tampered, aad)
        msg = str(excinfo.value).lower()
        # Must NOT reveal whether tag, key, or AAD caused the failure.
        assert "decryption failed" in msg

    def test_aad_mismatch_fails(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        ciphertext = cipher.encrypt(b"secret", b"aad-A")

        with pytest.raises(ValueError):
            cipher.decrypt(ciphertext, b"aad-B")

    def test_wrong_key_fails(self) -> None:
        cipher_a = EmbeddingCipher(_fresh_kek_b64())
        cipher_b = EmbeddingCipher(_fresh_kek_b64())
        ciphertext = cipher_a.encrypt(b"secret", b"aad")

        with pytest.raises(ValueError):
            cipher_b.decrypt(ciphertext, b"aad")

    def test_missing_prefix_fails(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        with pytest.raises(ValueError, match="enc:v1:"):
            cipher.decrypt("not-a-ciphertext", b"aad")

    def test_malformed_base64_fails(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        with pytest.raises(ValueError, match="base64"):
            cipher.decrypt(f"{CIPHERTEXT_PREFIX}***not-base64***", b"aad")

    def test_payload_too_short_fails(self) -> None:
        cipher = EmbeddingCipher(_fresh_kek_b64())
        short = base64.b64encode(b"too short").decode("ascii")
        with pytest.raises(ValueError, match="shorter than"):
            cipher.decrypt(f"{CIPHERTEXT_PREFIX}{short}", b"aad")


class TestEmbeddingCipherInitFailFast:
    def test_missing_key_raises(self) -> None:
        with pytest.raises(ValueError, match="not configured"):
            EmbeddingCipher("")
        with pytest.raises(ValueError, match="not configured"):
            EmbeddingCipher("   ")

    def test_non_base64_key_raises(self) -> None:
        with pytest.raises(ValueError, match="base64"):
            EmbeddingCipher("this is not base64 @@@")

    def test_wrong_length_key_raises(self) -> None:
        too_short = base64.b64encode(b"only-16-bytes!!!!").decode("ascii")
        with pytest.raises(ValueError, match="32 bytes"):
            EmbeddingCipher(too_short)

        too_long = base64.b64encode(os.urandom(64)).decode("ascii")
        with pytest.raises(ValueError, match="32 bytes"):
            EmbeddingCipher(too_long)

    def test_key_value_not_leaked_in_errors(self) -> None:
        """The KEK must never appear in exception text."""
        secret_kek = base64.b64encode(b"A" * 48).decode("ascii")  # wrong length
        try:
            EmbeddingCipher(secret_kek)
        except ValueError as exc:
            assert secret_kek not in str(exc)
            assert "A" * 10 not in str(exc)


class TestEmbeddingCipherFingerprint:
    def test_fingerprint_is_deterministic_per_kek(self) -> None:
        kek = _fresh_kek_b64()
        c1 = EmbeddingCipher(kek)
        c2 = EmbeddingCipher(kek)
        assert c1.key_fingerprint == c2.key_fingerprint
        assert len(c1.key_fingerprint) == 8

    def test_fingerprint_differs_across_keks(self) -> None:
        c1 = EmbeddingCipher(_fresh_kek_b64())
        c2 = EmbeddingCipher(_fresh_kek_b64())
        assert c1.key_fingerprint != c2.key_fingerprint
