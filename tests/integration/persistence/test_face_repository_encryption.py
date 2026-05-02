"""Integration-style tests for repository × EmbeddingCipher wiring (P1.3).

These tests don't hit a real Postgres — instead they install an asyncpg
``Pool``/``Connection`` double so we can assert that:

  1. ``save()`` passes a ``bytes`` ciphertext to the INSERT statement.
  2. The ciphertext round-trips through :class:`EmbeddingCipher` back to the
     original plaintext vector.
  3. ``key_version=1`` is written.
  4. The ciphertext is non-trivially different from the plaintext bytes.

A real DB integration test would live under ``tests/integration/`` proper and
require a live pgvector container; that's out of scope for the encryption PR
and lives behind the existing test infra TODOs.
"""

from __future__ import annotations

from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from cryptography.fernet import Fernet

from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
    PgVectorEmbeddingRepository,
)
from app.infrastructure.persistence.repositories.pgvector_voice_repository import (
    PgVectorVoiceRepository,
)
from app.infrastructure.security.embedding_cipher import EmbeddingCipher


def _make_conn_mock() -> tuple[MagicMock, List[tuple]]:
    """Build a connection-context-manager double and capture all execute() args."""
    captured: List[tuple] = []
    conn = MagicMock()

    async def _execute(*args: Any, **kwargs: Any) -> str:
        captured.append(args)
        return "INSERT 0 1"

    async def _fetchrow(*args: Any, **kwargs: Any) -> Any:
        # Used by save() to read back the SQL-side AVG centroid. Return a
        # plausible centroid vector and quality so the centroid branch runs.
        return {"avg_emb": np.zeros(512, dtype=np.float32).tolist(), "avg_q": 0.5}

    async def _fetchval(*args: Any, **kwargs: Any) -> int:
        # 0 → centroid does not exist yet → INSERT branch
        return 0

    conn.execute = AsyncMock(side_effect=_execute)
    conn.fetchrow = AsyncMock(side_effect=_fetchrow)
    conn.fetchval = AsyncMock(side_effect=_fetchval)
    return conn, captured


def _make_pool_double(conn: MagicMock) -> MagicMock:
    pool = MagicMock()

    class _AcquireCtx:
        async def __aenter__(self_inner) -> Any:
            return conn

        async def __aexit__(self_inner, *exc: Any) -> None:
            return None

    def _acquire() -> _AcquireCtx:
        return _AcquireCtx()

    pool.acquire = _acquire
    return pool


@pytest.fixture
def cipher() -> EmbeddingCipher:
    return EmbeddingCipher(key=Fernet.generate_key())


@pytest.mark.asyncio
async def test_face_save_writes_ciphertext_to_insert(cipher: EmbeddingCipher) -> None:
    repo = PgVectorEmbeddingRepository(
        database_url="postgresql://stub",
        embedding_dimension=512,
        cipher=cipher,
    )
    conn, captured = _make_conn_mock()
    pool = _make_pool_double(conn)

    rng = np.random.default_rng(seed=42)
    vec = rng.standard_normal(512).astype(np.float32)

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=pool)):
        await repo.save(
            user_id="user-1",
            embedding=vec,
            quality_score=0.9,
            tenant_id="tenant-a",
        )

    # First execute() call is the INDIVIDUAL insert. Find a ciphertext bytes
    # arg of plausible length. Fernet tokens for a 512*4-byte payload are well
    # over 100 bytes.
    individual_call = captured[0]
    sql = individual_call[0]
    assert "embedding_ciphertext" in sql
    assert "key_version" in sql

    bytes_args = [a for a in individual_call[1:] if isinstance(a, (bytes, bytearray))]
    assert bytes_args, "no ciphertext arg captured"
    ciphertext = bytes(bytes_args[0])

    # Round-trip confirms the cipher wired to the repo is the one writing.
    decrypted = cipher.decrypt_vector(ciphertext)
    np.testing.assert_array_equal(decrypted, vec)

    # Sanity: ciphertext should not contain raw float bytes verbatim.
    assert vec.tobytes()[:32] not in ciphertext

    # key_version must be present and equal to 1 in the INSERT args.
    assert 1 in individual_call[1:]


@pytest.mark.asyncio
async def test_voice_save_writes_ciphertext_to_insert(cipher: EmbeddingCipher) -> None:
    repo = PgVectorVoiceRepository(
        database_url="postgresql://stub",
        embedding_dimension=256,
        cipher=cipher,
    )
    conn, captured = _make_conn_mock()
    pool = _make_pool_double(conn)

    rng = np.random.default_rng(seed=7)
    vec = rng.standard_normal(256).astype(np.float32)

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=pool)):
        await repo.save(
            user_id="user-2",
            embedding=vec,
            quality_score=0.85,
            tenant_id="tenant-a",
        )

    individual_call = captured[0]
    sql = individual_call[0]
    assert "embedding_ciphertext" in sql
    assert "key_version" in sql

    bytes_args = [a for a in individual_call[1:] if isinstance(a, (bytes, bytearray))]
    assert bytes_args, "no ciphertext arg captured"
    decrypted = cipher.decrypt_vector(bytes(bytes_args[0]))
    np.testing.assert_array_equal(decrypted, vec)
