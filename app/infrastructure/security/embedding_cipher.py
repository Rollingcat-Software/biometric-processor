"""Authenticated encryption for face / voice biometric embeddings at rest.

GDPR Article 9 requires "appropriate technical and organisational measures"
for biometric data; we encrypt the raw embedding bytes before persistence.

Architectural note: pgvector's ANN similarity search (`<=>`) operates on
plaintext vectors. The vector cannot be encrypted in place without breaking
search. We therefore use a **dual-column** model:

  * ``embedding`` (pgvector) — derived ANN index, kept warm for search.
  * ``embedding_ciphertext`` (bytea) — canonical store-of-record. Always
    written. Plaintext can be re-derived from this column.

For this PR the key is a single ``FIVUCSAS_EMBEDDING_KEY`` env var (Fernet
URL-safe base64). The schema reserves a ``key_version`` smallint and a
nullable future ``tenant_dek_id`` so per-tenant DEKs can be added later
without another schema change.
"""

from __future__ import annotations

import os
import struct
from typing import Optional

import numpy as np
from cryptography.fernet import Fernet, InvalidToken

_KEY_ENV = "FIVUCSAS_EMBEDDING_KEY"

# 4-byte big-endian length header followed by float32 vector bytes.
# Keeps overhead minimal vs. JSON/pickle and gives us self-describing length
# so callers don't need to remember the model dimension to decrypt.
_HEADER_FMT = ">I"
_HEADER_LEN = struct.calcsize(_HEADER_FMT)


class EmbeddingCipher:
    """Symmetric authenticated encryption (Fernet / AES-128-CBC + HMAC-SHA256).

    Why Fernet (not AES-GCM directly):
        * stdlib via ``cryptography``; already a transitive dep
        * built-in IV management and HMAC integrity check
        * versioned token format — easier to rotate later
    """

    def __init__(self, key: Optional[bytes | str] = None) -> None:
        raw = key if key is not None else os.environ.get(_KEY_ENV, "")
        if not raw:
            raise RuntimeError(
                f"{_KEY_ENV} is not set. Generate one via "
                f"`python -c 'from cryptography.fernet import Fernet; "
                f"print(Fernet.generate_key().decode())'`"
            )
        if isinstance(raw, str):
            raw = raw.encode("ascii")
        # Will raise binascii.Error / ValueError if not valid Fernet key.
        self._fernet = Fernet(raw)

    @classmethod
    def from_env(cls) -> "EmbeddingCipher":
        """Build cipher from process env. Fails fast if key is missing."""
        return cls()

    def encrypt_vector(self, vec: np.ndarray) -> bytes:
        """Encrypt a 1-D numpy float32 vector. Returns Fernet ciphertext bytes."""
        if vec.ndim != 1:
            raise ValueError(f"Expected 1-D vector, got shape {vec.shape}")
        if vec.dtype != np.float32:
            vec = vec.astype(np.float32, copy=False)
        # length-prefixed payload: u32 element count + raw bytes
        payload = struct.pack(_HEADER_FMT, vec.size) + vec.tobytes(order="C")
        return self._fernet.encrypt(payload)

    def decrypt_vector(self, blob: bytes) -> np.ndarray:
        """Decrypt and return a fresh float32 numpy array.

        Raises ``RuntimeError`` on integrity failure — caller should treat
        this as an irrecoverable data corruption / wrong-key event.
        """
        try:
            payload = self._fernet.decrypt(blob)
        except InvalidToken as e:
            raise RuntimeError(
                "Embedding ciphertext failed integrity check "
                "(wrong key, corruption, or tampering)"
            ) from e
        if len(payload) < _HEADER_LEN:
            raise RuntimeError("Embedding ciphertext payload truncated")
        (n,) = struct.unpack(_HEADER_FMT, payload[:_HEADER_LEN])
        body = payload[_HEADER_LEN:]
        expected_bytes = n * np.dtype(np.float32).itemsize
        if len(body) != expected_bytes:
            raise RuntimeError(
                f"Embedding ciphertext length mismatch: "
                f"header says {n} float32s ({expected_bytes} bytes), "
                f"got {len(body)} bytes"
            )
        # frombuffer returns a read-only view over an immutable bytes object;
        # caller almost always wants a writable array, so .copy() it.
        return np.frombuffer(body, dtype=np.float32, count=n).copy()
