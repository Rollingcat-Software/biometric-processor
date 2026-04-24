"""Add envelope-encrypted ciphertext columns for face + voice embeddings.

Revision ID: 0005_add_embedding_ciphertext_columns
Revises: 0004_client_embedding_observations
Create Date: 2026-04-20

Phase 1.3b (Audit 2026-04-19 remediation) — KVKK Decision 2018/10 requires
biometric data to be cryptographically stored with keys held in a secure
environment. Volume-level TDE is not sufficient.

This migration is additive:

* Adds ``embedding_ciphertext BYTEA`` + ``embedding_iv BYTEA`` +
  ``enc_version SMALLINT`` columns to both ``face_embeddings`` and
  ``voice_enrollments``.
* Creates ``tenant_deks`` (tenant_id PRIMARY KEY, wrapped_dek BYTEA, iv
  BYTEA, created_at TIMESTAMPTZ DEFAULT now()).

No existing data is rewritten and no existing column is dropped. See
``0006_backfill_embedding_ciphertext`` (gated backfill) and
``0007_drop_plaintext_embedding_columns`` (irreversible cutover) for the
next steps of the migration plan.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0005_add_embedding_ciphertext_columns"
down_revision: Union[str, None] = "0004_client_embedding_observations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ciphertext columns and tenant_deks table."""

    # ---- face_embeddings ------------------------------------------------
    op.execute(
        """
        ALTER TABLE face_embeddings
            ADD COLUMN IF NOT EXISTS embedding_ciphertext BYTEA,
            ADD COLUMN IF NOT EXISTS embedding_iv BYTEA,
            ADD COLUMN IF NOT EXISTS enc_version SMALLINT
        """
    )

    # ---- voice_enrollments ---------------------------------------------
    op.execute(
        """
        ALTER TABLE voice_enrollments
            ADD COLUMN IF NOT EXISTS embedding_ciphertext BYTEA,
            ADD COLUMN IF NOT EXISTS embedding_iv BYTEA,
            ADD COLUMN IF NOT EXISTS enc_version SMALLINT
        """
    )

    # ---- tenant_deks ----------------------------------------------------
    # Each tenant gets one DEK wrapped by the env-sourced KEK.
    # ``wrapped_dek`` stores the ``enc:v1:<base64>`` payload as ASCII bytes.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_deks (
            tenant_id UUID PRIMARY KEY,
            wrapped_dek BYTEA NOT NULL,
            iv BYTEA NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    """Reverse the additive changes. Safe to run on a partially-migrated DB."""
    op.execute("DROP TABLE IF EXISTS tenant_deks")

    op.execute(
        """
        ALTER TABLE voice_enrollments
            DROP COLUMN IF EXISTS enc_version,
            DROP COLUMN IF EXISTS embedding_iv,
            DROP COLUMN IF EXISTS embedding_ciphertext
        """
    )

    op.execute(
        """
        ALTER TABLE face_embeddings
            DROP COLUMN IF EXISTS enc_version,
            DROP COLUMN IF EXISTS embedding_iv,
            DROP COLUMN IF EXISTS embedding_ciphertext
        """
    )
