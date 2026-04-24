"""Drop plaintext embedding columns and pgvector indexes (IRREVERSIBLE).

Revision ID: 0007_drop_plaintext_embedding_columns
Revises: 0006_backfill_embedding_ciphertext
Create Date: 2026-04-20

Phase 1.3b (Audit 2026-04-19 remediation) — final cutover to
ciphertext-only storage.

**This migration is IRREVERSIBLE.** After it runs, the plaintext
``embedding`` column is physically removed from ``face_embeddings`` and
``voice_enrollments``. The pgvector HNSW and IVFFlat indexes are dropped
because they can no longer operate on ciphertext. Matching is now handled
by :class:`app.security.embedding_match.EmbeddingMatchService`.

Operator checklist (MUST complete in order)
-------------------------------------------
1. Migration 0005 applied.
2. Migration 0006 applied with ``FIVUCSAS_EMBEDDING_MIGRATE=true`` and
   zero remaining plaintext-only rows.
3. Service running at least one release with
   ``FIVUCSAS_EMBEDDING_ENC_ENABLED=true`` and
   ``FIVUCSAS_EMBEDDING_ENC_STRICT=false`` (dual-read/dual-write window).
4. Verified that ``EmbeddingMatchService.search_top_k`` returns results
   parity-matching the pgvector path for all tenants (integration test
   ``test_encrypted_match_parity``).

Only then run::

    FIVUCSAS_EMBEDDING_ENC_STRICT=true alembic upgrade \
        0007_drop_plaintext_embedding_columns

The gate on ``FIVUCSAS_EMBEDDING_ENC_STRICT`` prevents an operator from
applying this migration before the dual-read window has been validated.
"""

from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0007_drop_plaintext_embedding_columns"
down_revision: Union[str, None] = "0006_backfill_embedding_ciphertext"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop pgvector indexes and plaintext ``embedding`` columns."""
    strict = os.getenv("FIVUCSAS_EMBEDDING_ENC_STRICT", "").strip().lower()
    if strict != "true":
        raise RuntimeError(
            "0007_drop_plaintext_embedding_columns is IRREVERSIBLE and must "
            "only be applied after the dual-read window. "
            "Set FIVUCSAS_EMBEDDING_ENC_STRICT=true explicitly to proceed."
        )

    # Drop vector indexes — they are useless on ciphertext.
    op.execute("DROP INDEX IF EXISTS ix_biometric_data_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector_ivfflat")
    op.execute("DROP INDEX IF EXISTS idx_voice_embeddings_ivfflat")

    # Drop plaintext columns.
    op.execute("ALTER TABLE face_embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE voice_enrollments DROP COLUMN IF EXISTS embedding")

    # Replacement access indexes — match service still needs efficient
    # per-tenant row selection when rebuilding its in-memory matrix.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_face_embeddings_tenant_user
        ON face_embeddings (tenant_id, user_id)
        WHERE deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_voice_enrollments_tenant_user
        ON voice_enrollments (tenant_id, user_id)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:  # pragma: no cover - irreversible
    raise RuntimeError(
        "Migration 0007 is irreversible by design. Restore from backup if "
        "you must recover plaintext embeddings (and rotate the KEK)."
    )
