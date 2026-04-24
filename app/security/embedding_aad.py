"""Shared AAD + serialization helpers for encrypted biometric embeddings.

Three call sites need to agree on AAD construction byte-for-byte:

* :class:`app.infrastructure.persistence.repositories.pgvector_embedding_repository.PgVectorEmbeddingRepository`
  (face writes and reads)
* :class:`app.infrastructure.persistence.repositories.pgvector_voice_repository.PgVectorVoiceRepository`
  (voice writes and reads)
* :class:`app.security.embedding_match.EmbeddingMatchService` (top-k reads
  over the decrypted per-tenant matrix)

If any of these drift the auth tag fails and rows become unreadable. The
helpers live here so the definition of "modality-tagged, tenant-bound,
user-bound AAD" is single-sourced — no service or repository should
rebuild the byte string itself.
"""

from __future__ import annotations

import hashlib
from typing import Final, Optional
from uuid import UUID

import numpy as np


MODALITY_FACE: Final[str] = "face"
MODALITY_VOICE: Final[str] = "voice"
ALLOWED_MODALITIES: Final[frozenset[str]] = frozenset({MODALITY_FACE, MODALITY_VOICE})

_NULL_TENANT_UUID_BYTES: Final[bytes] = b"\x00" * 16
_AAD_SEPARATOR: Final[bytes] = b":"


def tenant_uuid(tenant_id: Optional[str]) -> Optional[UUID]:
    """Return the ``UUID`` for ``tenant_id``.

    UUID-shaped inputs parse directly. Legacy or test string tenant IDs
    that aren't valid UUIDs are hashed to a deterministic 16-byte UUID
    so the AAD remains stable for the same tenant across processes.
    """
    if tenant_id is None:
        return None
    try:
        return UUID(str(tenant_id))
    except (ValueError, AttributeError):
        digest = hashlib.sha256(str(tenant_id).encode("utf-8")).digest()[:16]
        return UUID(bytes=digest)


def embedding_aad(
    modality: str, tenant_id: Optional[str], user_id: str
) -> bytes:
    """Return ``<modality>:<tenant_uuid_bytes>:<user_id_bytes>``.

    Raises
    ------
    ValueError
        When ``modality`` is neither ``"face"`` nor ``"voice"``.
    """
    if modality not in ALLOWED_MODALITIES:
        raise ValueError(
            f"modality must be one of {sorted(ALLOWED_MODALITIES)}, got {modality!r}"
        )
    tu = tenant_uuid(tenant_id)
    tenant_bytes = tu.bytes if tu is not None else _NULL_TENANT_UUID_BYTES
    return (
        modality.encode("ascii")
        + _AAD_SEPARATOR
        + tenant_bytes
        + _AAD_SEPARATOR
        + user_id.encode("utf-8")
    )


def embedding_to_bytes(vec: np.ndarray) -> bytes:
    """Serialize a 1-D array to little-endian float32 bytes."""
    return np.asarray(vec, dtype=np.float32).tobytes()


def bytes_to_embedding(raw: bytes, dim: int) -> np.ndarray:
    """Deserialize little-endian float32 bytes back to a 1-D numpy array.

    Raises
    ------
    ValueError
        If the recovered vector's size does not match ``dim``.
    """
    vec = np.frombuffer(raw, dtype=np.float32)
    if vec.size != dim:
        raise ValueError(
            f"Decrypted embedding has wrong dimension: expected {dim}, got {vec.size}"
        )
    return vec
