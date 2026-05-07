"""Integration-style tests for repository × EmbeddingCipher wiring (P1.3).

These tests don't hit a real Postgres — instead they install an asyncpg
``Pool``/``Connection`` double so we can assert that:

  1. ``save()`` passes a ``bytes`` ciphertext to the INSERT statement.
  2. The ciphertext round-trips through :class:`EmbeddingCipher` back to the
     original plaintext vector.
  3. ``key_version=1`` is written.
  4. The ciphertext is non-trivially different from the plaintext bytes.

P0-#2 (2026-05-07) — read-path coverage:

  5. ``find_by_user_id()`` SELECTs the ciphertext column and prefers the
     **decrypted** value over the plaintext ANN column.
  6. ``find_by_user_id()`` falls back to the plaintext column only when the
     ciphertext is NULL (legacy / pre-backfill rows).
  7. Save → find_by_user_id → find_similar end-to-end: enroll user A and
     verify the round-tripped embedding is what subsequent identification
     would use, proving the decryption layer is wired into the read path.

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


# ---------------------------------------------------------------------------
# P0-#2 (2026-05-07): read-path uses ciphertext, not plaintext column.
# ---------------------------------------------------------------------------


def _make_read_pool(row_payload: dict | None) -> MagicMock:
    """Build an asyncpg pool double that returns ``row_payload`` from fetchrow."""
    conn = MagicMock()

    async def _fetchrow(*args: Any, **kwargs: Any) -> Any:
        return row_payload

    async def _fetch(*args: Any, **kwargs: Any) -> list:
        return [row_payload] if row_payload is not None else []

    conn.fetchrow = AsyncMock(side_effect=_fetchrow)
    conn.fetch = AsyncMock(side_effect=_fetch)
    return _make_pool_double(conn)


@pytest.mark.asyncio
async def test_face_find_by_user_id_decrypts_ciphertext(cipher: EmbeddingCipher) -> None:
    """P0-#2: find_by_user_id MUST prefer the decrypted ciphertext.

    The plaintext ``embedding`` column is poisoned with all-zeros so that any
    fall-through to the legacy path would yield a vector visibly different
    from the original. Only a real decrypt of the ciphertext column produces
    the expected vector.
    """
    repo = PgVectorEmbeddingRepository(
        database_url="postgresql://stub",
        embedding_dimension=512,
        cipher=cipher,
    )

    rng = np.random.default_rng(seed=2026)
    original = rng.standard_normal(512).astype(np.float32)
    ciphertext = cipher.encrypt_vector(original)

    poisoned_plaintext = np.zeros(512, dtype=np.float32).tolist()
    row = {"embedding": poisoned_plaintext, "embedding_ciphertext": ciphertext}
    pool = _make_read_pool(row)

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=pool)):
        out = await repo.find_by_user_id(user_id="user-A", tenant_id="tenant-a")

    assert out is not None
    np.testing.assert_array_equal(out, original)
    # Defensive: not the poisoned plaintext.
    assert not np.array_equal(out, np.zeros(512, dtype=np.float32))


@pytest.mark.asyncio
async def test_face_find_by_user_id_falls_back_to_plaintext_when_ciphertext_null(
    cipher: EmbeddingCipher,
) -> None:
    """Legacy rows (pre-P1.3) have NULL ciphertext — must still resolve.

    Forward-compat fallback: until we run the Option B drop-plaintext
    migration we still need to read pre-encryption rows. This test pins
    that behavior so the fallback can't be removed accidentally.
    """
    repo = PgVectorEmbeddingRepository(
        database_url="postgresql://stub",
        embedding_dimension=512,
        cipher=cipher,
    )

    rng = np.random.default_rng(seed=99)
    legacy_plain = rng.standard_normal(512).astype(np.float32)
    row = {"embedding": legacy_plain.tolist(), "embedding_ciphertext": None}
    pool = _make_read_pool(row)

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=pool)):
        out = await repo.find_by_user_id(user_id="legacy-user", tenant_id="tenant-a")

    assert out is not None
    np.testing.assert_allclose(out, legacy_plain)


@pytest.mark.asyncio
async def test_face_save_then_find_round_trip_is_decrypt_path(
    cipher: EmbeddingCipher,
) -> None:
    """End-to-end: save() encrypts, find_by_user_id() decrypts, vectors match.

    This is the canonical proof that the encryption layer is *integrated*
    end-to-end in the read path — not just written and ignored. The
    captured ciphertext from save() is fed back into find_by_user_id()'s
    fetchrow, with a poisoned plaintext column. A passing test means the
    repository round-trips through Fernet on the way out.
    """
    repo = PgVectorEmbeddingRepository(
        database_url="postgresql://stub",
        embedding_dimension=512,
        cipher=cipher,
    )

    rng = np.random.default_rng(seed=7777)
    vec = rng.standard_normal(512).astype(np.float32)

    # ---- save(): capture the ciphertext written to the INSERT ----------------
    save_conn, save_captured = _make_conn_mock()
    save_pool = _make_pool_double(save_conn)
    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=save_pool)):
        await repo.save(
            user_id="user-A",
            embedding=vec,
            quality_score=0.95,
            tenant_id="tenant-a",
        )
    insert_args = save_captured[0]
    written_ciphertext = next(
        bytes(a) for a in insert_args[1:] if isinstance(a, (bytes, bytearray))
    )

    # ---- find_by_user_id(): poison the plaintext, hand back ciphertext -------
    poisoned_plaintext = np.zeros(512, dtype=np.float32).tolist()
    read_row = {"embedding": poisoned_plaintext, "embedding_ciphertext": written_ciphertext}
    read_pool = _make_read_pool(read_row)
    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=read_pool)):
        recovered = await repo.find_by_user_id(user_id="user-A", tenant_id="tenant-a")

    assert recovered is not None
    np.testing.assert_array_equal(recovered, vec)


@pytest.mark.asyncio
async def test_voice_find_by_user_id_decrypts_ciphertext(cipher: EmbeddingCipher) -> None:
    """Mirror of the face read-path test for voice embeddings (256-dim)."""
    repo = PgVectorVoiceRepository(
        database_url="postgresql://stub",
        embedding_dimension=256,
        cipher=cipher,
    )

    rng = np.random.default_rng(seed=2027)
    original = rng.standard_normal(256).astype(np.float32)
    ciphertext = cipher.encrypt_vector(original)

    poisoned_plaintext = np.zeros(256, dtype=np.float32).tolist()
    row = {"embedding": poisoned_plaintext, "embedding_ciphertext": ciphertext}
    pool = _make_read_pool(row)

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=pool)):
        out = await repo.find_by_user_id(user_id="voice-A", tenant_id="tenant-a")

    assert out is not None
    np.testing.assert_array_equal(out, original)


@pytest.mark.asyncio
async def test_face_get_all_by_tenant_decrypts_ciphertext(cipher: EmbeddingCipher) -> None:
    """``get_all_by_tenant`` paginates through stored embeddings; each row's
    ciphertext column must be the source-of-truth, not the plaintext column."""
    repo = PgVectorEmbeddingRepository(
        database_url="postgresql://stub",
        embedding_dimension=512,
        cipher=cipher,
    )

    rng = np.random.default_rng(seed=4242)
    original = rng.standard_normal(512).astype(np.float32)
    ciphertext = cipher.encrypt_vector(original)
    poisoned_plaintext = np.zeros(512, dtype=np.float32).tolist()

    row = {
        "user_id": "user-X",
        "embedding": poisoned_plaintext,
        "embedding_ciphertext": ciphertext,
        "quality_score": 0.9,
        "created_at": None,
        "updated_at": None,
    }
    pool = _make_read_pool(row)

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=pool)):
        rows = await repo.get_all_by_tenant(tenant_id="tenant-a", limit=10, offset=0)

    assert len(rows) == 1
    np.testing.assert_array_equal(rows[0]["embedding"], original)
