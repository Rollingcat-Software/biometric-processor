"""Backfill ciphertext columns for existing plaintext embeddings (gated).

Revision ID: 0006_backfill_embedding_ciphertext
Revises: 0005_add_embedding_ciphertext_columns
Create Date: 2026-04-20

Phase 1.3b (Audit 2026-04-19 remediation) — encrypt every pre-existing
``face_embeddings.embedding`` and ``voice_enrollments.embedding`` value
into the new ``embedding_ciphertext`` column.

Operator runbook
----------------
1. Ensure ``FIVUCSAS_EMBEDDING_KEK`` is set in the environment the
   Alembic command will run with. The same KEK must be used by the
   running biometric-processor.
2. Run::

       FIVUCSAS_EMBEDDING_MIGRATE=true \
         FIVUCSAS_EMBEDDING_KEK="$(cat /run/secrets/embedding_kek.b64)" \
         alembic upgrade 0006_backfill_embedding_ciphertext

3. Verify zero plaintext rows remain without ciphertext::

       SELECT count(*) FROM face_embeddings
         WHERE embedding IS NOT NULL AND embedding_ciphertext IS NULL;
       SELECT count(*) FROM voice_enrollments
         WHERE embedding IS NOT NULL AND embedding_ciphertext IS NULL;

4. Flip ``FIVUCSAS_EMBEDDING_ENC_ENABLED=true`` in the service env
   (dual-read window). Only then run migration 0007 to drop the
   plaintext columns.

Safety
------
* Idempotent. Rows whose ``embedding_ciphertext`` is already populated
  are skipped. Re-running is a safe no-op.
* Batched (2000 rows at a time) to keep transaction size bounded.
* Gated by ``FIVUCSAS_EMBEDDING_MIGRATE`` env var (must equal ``"true"``
  case-insensitive). Any other value → no-op.
* Reads the KEK from ``FIVUCSAS_EMBEDDING_KEK``; fail-fast if empty
  whenever the gate is on.
"""

from __future__ import annotations

import logging
import os
import struct
from typing import Sequence, Union
from uuid import UUID

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0006_backfill_embedding_ciphertext"
down_revision: Union[str, None] = "0005_add_embedding_ciphertext_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger(__name__)


BATCH_SIZE = 2000


def _gate_enabled() -> bool:
    return os.getenv("FIVUCSAS_EMBEDDING_MIGRATE", "").strip().lower() == "true"


def _pgvector_text_to_bytes(value: object) -> bytes:
    """Convert a pgvector value (rendered as Python list or ``"[...]"``
    string) to the little-endian float32 byte layout used by
    ``EmbeddingCipher``/``EmbeddingMatchService``.
    """
    if value is None:
        return b""
    if isinstance(value, (list, tuple)):
        floats = [float(x) for x in value]
    elif isinstance(value, str):
        stripped = value.strip().strip("[]")
        if not stripped:
            return b""
        floats = [float(x) for x in stripped.split(",")]
    else:
        # asyncpg with register_vector yields numpy arrays; we are not in an
        # async context here — fall back to str() parsing.
        raise TypeError(f"Unsupported pgvector value type: {type(value)!r}")
    return struct.pack(f"<{len(floats)}f", *floats)


def _aad(modality: str, tenant_id: UUID | None, user_id: str) -> bytes:
    tb = tenant_id.bytes if tenant_id is not None else b"\x00" * 16
    return modality.encode("ascii") + b":" + tb + b":" + user_id.encode("utf-8")


def upgrade() -> None:
    """Encrypt plaintext rows into ``embedding_ciphertext``."""
    if not _gate_enabled():
        logger.warning(
            "0006_backfill_embedding_ciphertext: FIVUCSAS_EMBEDDING_MIGRATE "
            "is not 'true' — no-op. Set FIVUCSAS_EMBEDDING_MIGRATE=true to "
            "run the backfill."
        )
        op.execute("SELECT 1")
        return

    # Imported lazily so "no-op" mode works even in environments that have
    # not installed our module tree on the alembic path.
    from app.security.embedding_cipher import EmbeddingCipher  # noqa: WPS433

    kek = os.getenv("FIVUCSAS_EMBEDDING_KEK", "")
    if not kek.strip():
        raise RuntimeError(
            "FIVUCSAS_EMBEDDING_KEK must be set when "
            "FIVUCSAS_EMBEDDING_MIGRATE=true."
        )

    cipher = EmbeddingCipher(kek_b64=kek)
    conn = op.get_bind()

    for modality, table in (("face", "face_embeddings"), ("voice", "voice_enrollments")):
        total = 0
        while True:
            # Pull a batch of rows that still need ciphertext. The primary
            # key column for both tables is ``id``.
            rows = conn.execute(
                _make_select(table, BATCH_SIZE)
            ).fetchall()
            if not rows:
                break

            updates = []
            for row in rows:
                row_id = row._mapping["id"]
                user_id = row._mapping["user_id"]
                tenant_id_raw = row._mapping["tenant_id"]
                embedding_value = row._mapping["embedding"]

                tenant_uuid: UUID | None
                if tenant_id_raw is None:
                    tenant_uuid = None
                elif isinstance(tenant_id_raw, UUID):
                    tenant_uuid = tenant_id_raw
                else:
                    tenant_uuid = UUID(str(tenant_id_raw))

                try:
                    plaintext = _pgvector_text_to_bytes(embedding_value)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error(
                        "0006 backfill: failed to parse vector for "
                        "%s id=%s (%s) — skipping",
                        table, row_id, exc,
                    )
                    continue

                if not plaintext:
                    continue

                ct = cipher.encrypt(plaintext, _aad(modality, tenant_uuid, str(user_id)))
                updates.append((ct.encode("ascii"), row_id))

            if not updates:
                # Nothing encryptable in this batch; break to avoid infinite
                # loop on unreadable rows.
                break

            for ct_bytes, row_id in updates:
                conn.execute(
                    _make_update(table),
                    {"ct": ct_bytes, "id": row_id},
                )
            total += len(updates)
            logger.info(
                "0006 backfill: %s — encrypted %d rows (running total %d)",
                table, len(updates), total,
            )

            if len(rows) < BATCH_SIZE:
                break

        logger.info("0006 backfill: %s — completed, %d rows encrypted", table, total)


def downgrade() -> None:
    """Clear the ciphertext columns (plaintext is unchanged, so this is
    reversible)."""
    op.execute(
        """
        UPDATE face_embeddings
        SET embedding_ciphertext = NULL,
            embedding_iv = NULL,
            enc_version = NULL
        WHERE embedding_ciphertext IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE voice_enrollments
        SET embedding_ciphertext = NULL,
            embedding_iv = NULL,
            enc_version = NULL
        WHERE embedding_ciphertext IS NOT NULL
        """
    )


def _make_select(table: str, limit: int):
    from sqlalchemy import text

    return text(
        f"""
        SELECT id, user_id, tenant_id, embedding
        FROM {table}
        WHERE embedding IS NOT NULL
          AND embedding_ciphertext IS NULL
        ORDER BY id
        LIMIT {limit}
        """
    )


def _make_update(table: str):
    from sqlalchemy import text

    return text(
        f"""
        UPDATE {table}
        SET embedding_ciphertext = :ct,
            enc_version = 1
        WHERE id = :id
        """
    )
