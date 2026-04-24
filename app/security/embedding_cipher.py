"""AES-GCM-256 cipher for biometric embeddings (Phase 1.3b).

Mirrors the Java :code:`TotpSecretCipher` contract so operational runbooks,
key-rotation procedures, and forensic tooling can be shared between the two
services.

Storage format (value returned by :meth:`EmbeddingCipher.encrypt`)::

    enc:v1:<base64(iv || ciphertext || tag)>

Where:
    * ``iv`` — 12 random bytes from :class:`os.urandom`, never reused.
    * ``ciphertext`` — AES-256 in GCM mode.
    * ``tag`` — 128-bit GCM authentication tag (appended by
      :class:`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
    * AAD — caller-supplied, typically ``tenant_id || user_id`` bytes so
      that moving a ciphertext between tenants invalidates the auth tag.

Fail-fast rules (KEK must be present and well-formed at construction time):
    * Missing or blank KEK → :class:`ValueError`.
    * Non-base64 KEK → :class:`ValueError`.
    * KEK that does not decode to exactly 32 bytes → :class:`ValueError`.

Exceptions raised at runtime MUST NOT include key material or the
ciphertext payload. Tamper / wrong-key / AAD mismatch all surface as a
single generic ``"decryption failed"`` :class:`ValueError`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import os
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


CIPHERTEXT_PREFIX: Final[str] = "enc:v1:"
IV_LENGTH_BYTES: Final[int] = 12
TAG_LENGTH_BYTES: Final[int] = 16  # 128-bit GCM tag
KEY_LENGTH_BYTES: Final[int] = 32  # AES-256


class EmbeddingCipher:
    """AES-GCM-256 envelope cipher for embedding bytes.

    Parameters
    ----------
    kek_b64:
        Base64-encoded 32-byte Key Encryption Key. Must be non-empty and
        decode to exactly 32 bytes, else construction raises
        :class:`ValueError`.
    strict_mode:
        When ``True``, callers of dual-read paths (repositories) should
        refuse to read legacy plaintext rows. The cipher itself does not
        gate on this flag — it is retained on the instance so repositories
        can make a consistent decision without re-reading settings.
    """

    def __init__(self, kek_b64: str, strict_mode: bool = False) -> None:
        if kek_b64 is None or not str(kek_b64).strip():
            raise ValueError(
                "FIVUCSAS_EMBEDDING_KEK is not configured. "
                "Generate one with: openssl rand -base64 32"
            )

        try:
            key_bytes = base64.b64decode(kek_b64.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            # Do NOT echo the KEK value in the exception text.
            raise ValueError(
                "FIVUCSAS_EMBEDDING_KEK is not valid base64 "
                "(expected base64-encoded 32 bytes)."
            ) from exc

        if len(key_bytes) != KEY_LENGTH_BYTES:
            raise ValueError(
                "FIVUCSAS_EMBEDDING_KEK must decode to exactly "
                f"{KEY_LENGTH_BYTES} bytes (got {len(key_bytes)}). "
                "Regenerate with: openssl rand -base64 32"
            )

        self._aesgcm = AESGCM(key_bytes)
        self._strict_mode = bool(strict_mode)
        self._fingerprint = self._compute_fingerprint(key_bytes)

        # Zero the local reference to the raw key bytes ASAP. AESGCM holds its
        # own copy internally; we do not need ours anymore.
        del key_bytes

        logger.info(
            "EmbeddingCipher initialized (AES-GCM-256, KEK fingerprint "
            "sha256[0..8]=%s, strict_mode=%s)",
            self._fingerprint,
            self._strict_mode,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def strict_mode(self) -> bool:
        """Return whether this cipher was constructed in strict mode."""
        return self._strict_mode

    @property
    def key_fingerprint(self) -> str:
        """Return the 8-hex-char SHA-256 fingerprint of the KEK."""
        return self._fingerprint

    def encrypt(self, plaintext: bytes, aad: bytes) -> str:
        """Encrypt ``plaintext`` and return the ``enc:v1:<base64>`` payload.

        Parameters
        ----------
        plaintext:
            Raw bytes to encrypt. For embeddings this is typically a
            ``numpy.ndarray.tobytes()`` representation.
        aad:
            Additional authenticated data bound to the ciphertext. The same
            value must be supplied to :meth:`decrypt` or the auth tag will
            fail. Use a structured form such as
            ``b"face:" + tenant_uuid_bytes + b":" + user_id_bytes``.

        Returns
        -------
        str
            ``enc:v1:<base64(iv || ct_with_tag)>``.

        Raises
        ------
        ValueError
            If ``plaintext`` or ``aad`` is not bytes.
        """
        if not isinstance(plaintext, (bytes, bytearray)):
            raise ValueError("plaintext must be bytes")
        if not isinstance(aad, (bytes, bytearray)):
            raise ValueError("aad must be bytes")

        iv = os.urandom(IV_LENGTH_BYTES)
        # AESGCM.encrypt appends the 16-byte tag to the ciphertext.
        ct_with_tag = self._aesgcm.encrypt(iv, bytes(plaintext), bytes(aad))
        payload = iv + ct_with_tag
        return CIPHERTEXT_PREFIX + base64.b64encode(payload).decode("ascii")

    def decrypt(self, stored: str, aad: bytes) -> bytes:
        """Decrypt a stored ``enc:v1:...`` payload.

        Parameters
        ----------
        stored:
            The value previously returned by :meth:`encrypt`.
        aad:
            The exact AAD that was supplied to :meth:`encrypt`. A mismatch
            surfaces as a generic decryption failure (auth-tag failure).

        Returns
        -------
        bytes
            The recovered plaintext.

        Raises
        ------
        ValueError
            On any of: not a string, missing ``enc:v1:`` prefix, non-base64
            payload, payload too short to contain iv+tag, or auth-tag /
            wrong-key / AAD-mismatch failure. The error message does NOT
            distinguish auth-tag failure from key mismatch to avoid a
            tamper oracle.
        """
        if not isinstance(stored, str):
            raise ValueError("stored ciphertext must be a string")
        if not isinstance(aad, (bytes, bytearray)):
            raise ValueError("aad must be bytes")
        if not self.is_encrypted(stored):
            raise ValueError("Malformed ciphertext: missing enc:v1: prefix")

        body = stored[len(CIPHERTEXT_PREFIX):]
        try:
            raw = base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Malformed ciphertext: not base64") from exc

        if len(raw) <= IV_LENGTH_BYTES + TAG_LENGTH_BYTES:
            raise ValueError("Malformed ciphertext: payload shorter than iv+tag")

        iv = raw[:IV_LENGTH_BYTES]
        ct_with_tag = raw[IV_LENGTH_BYTES:]
        try:
            return self._aesgcm.decrypt(iv, ct_with_tag, bytes(aad))
        except InvalidTag as exc:
            # Generic failure — do not leak whether it was a bad tag, wrong
            # key, or AAD mismatch.
            raise ValueError(
                "Embedding decryption failed (auth tag mismatch, wrong key, "
                "or AAD mismatch)"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("Embedding decryption failed") from exc

    @staticmethod
    def is_encrypted(value: object) -> bool:
        """Return ``True`` when ``value`` is a string carrying the ``enc:v1:``
        prefix. Accepts any type safely.
        """
        return isinstance(value, str) and value.startswith(CIPHERTEXT_PREFIX)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_fingerprint(key_bytes: bytes) -> str:
        """Return the first 4 bytes of SHA-256(key) as an 8-char hex digest."""
        return hashlib.sha256(key_bytes).hexdigest()[:8]
