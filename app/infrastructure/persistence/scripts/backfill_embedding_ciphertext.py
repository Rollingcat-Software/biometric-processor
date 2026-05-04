"""One-shot backfill of ``embedding_ciphertext`` for legacy rows (P1.3).

Reads every row in ``face_embeddings`` and ``voice_enrollments`` whose
``embedding_ciphertext`` is NULL, encrypts the existing plaintext vector
with the configured ``FIVUCSAS_EMBEDDING_KEY``, and writes it back in place.

Idempotent — rows that already have a non-null ciphertext are skipped.
Safe to re-run after a partial failure.

Usage (operator runs after migration + key set in .env.prod):

    docker compose -f docker-compose.prod.yml --env-file .env.prod \
        exec biometric-api \
        python -m app.infrastructure.persistence.scripts.backfill_embedding_ciphertext

Exit codes:
    0 — completed successfully (or nothing to do)
    1 — fatal error (key missing, DB unreachable, etc.)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Tuple

import asyncpg
import numpy as np

from app.infrastructure.security.embedding_cipher import EmbeddingCipher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("backfill_embedding_ciphertext")


PROGRESS_EVERY = 100
TABLES: Tuple[str, ...] = ("face_embeddings", "voice_enrollments")


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # asyncpg expects bare postgres URL, not the SQLAlchemy "+asyncpg" variant.
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _setup_connection(conn: asyncpg.Connection) -> None:
    from pgvector.asyncpg import register_vector
    await register_vector(conn)


def _coerce_embedding(raw) -> np.ndarray:
    """Normalize a pgvector column value into a float32 numpy array.

    pgvector returns the column as a Python string (e.g. ``'[0,0.024,0.149,...]'``)
    when the connection isn't registered with ``pgvector.asyncpg.register_vector``,
    and as a list/sequence when it is. Handle both — the registration call has
    historically been fragile across asyncpg/pgvector versions.
    """
    if isinstance(raw, str):
        raw = [float(x) for x in raw.strip("[]").split(",") if x]
    return np.array(raw, dtype=np.float32)


async def _backfill_table(
    conn: asyncpg.Connection, table: str, cipher: EmbeddingCipher, key_version: int
) -> Tuple[int, int]:
    """Returns (scanned, updated)."""
    scanned = 0
    updated = 0

    # NOTE: previous implementation used ``async for row in await conn.cursor(...)``
    # which raises ``TypeError: 'async for' requires an object with __aiter__``
    # against the asyncpg version pinned in this repo (Cursor lacks __aiter__).
    # ``conn.fetch`` materializes the result set in memory; current biometric_db
    # rowcounts are O(hundreds), so this is fine. If volume grows >100k, switch
    # to explicit cursor iteration via ``cursor.fetch(N)`` in a loop.
    rows = await conn.fetch(
        f"""
        SELECT id, embedding
        FROM {table}
        WHERE embedding_ciphertext IS NULL
          AND embedding IS NOT NULL
        ORDER BY id
        """
    )

    for row in rows:
        scanned += 1
        row_id = row["id"]
        try:
            vec = _coerce_embedding(row["embedding"])
            if vec.size == 0:
                logger.warning("%s id=%s has empty embedding; skipping", table, row_id)
                continue
            ciphertext = cipher.encrypt_vector(vec)
            await conn.execute(
                f"""
                UPDATE {table}
                SET embedding_ciphertext = $1,
                    key_version = $2
                WHERE id = $3
                  AND embedding_ciphertext IS NULL
                """,
                ciphertext, key_version, row_id,
            )
            updated += 1
        except Exception as e:  # noqa: BLE001 — keep going past one bad row
            logger.error("%s id=%s failed: %s", table, row_id, e)

        if scanned % PROGRESS_EVERY == 0:
            logger.info("%s: scanned=%d updated=%d", table, scanned, updated)

    logger.info("%s: DONE scanned=%d updated=%d", table, scanned, updated)
    return scanned, updated


async def main() -> int:
    try:
        cipher = EmbeddingCipher.from_env()
    except RuntimeError as e:
        logger.error("Cannot start: %s", e)
        return 1

    key_version = 1  # bump when per-tenant DEK lands

    try:
        conn = await asyncpg.connect(_database_url())
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to connect to DB: %s", e)
        return 1

    try:
        await _setup_connection(conn)
        totals_scanned = 0
        totals_updated = 0
        for table in TABLES:
            scanned, updated = await _backfill_table(conn, table, cipher, key_version)
            totals_scanned += scanned
            totals_updated += updated
        logger.info(
            "ALL DONE — scanned=%d updated=%d across %d tables",
            totals_scanned, totals_updated, len(TABLES),
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(main()))
