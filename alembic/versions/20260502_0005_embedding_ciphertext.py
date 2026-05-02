"""Add embedding_ciphertext + key_version columns for at-rest encryption.

Revision ID: 0005_embedding_ciphertext
Revises: 0004_client_embedding_observations
Create Date: 2026-05-02

GDPR Article 9 closure (P1.3). Plaintext pgvector column stays — pgvector ANN
similarity search requires it. The ciphertext column is the canonical
store-of-record; plaintext is treated as a derived ANN index.

Columns are added NULLable in this revision. After the operator backfills
existing rows via ``app.infrastructure.persistence.scripts.backfill_embedding_ciphertext``,
a follow-up revision can promote them to ``NOT NULL``.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0005_embedding_ciphertext"
down_revision: Union[str, None] = "0004_client_embedding_observations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ciphertext + key_version columns to face_embeddings + voice_enrollments."""

    # face_embeddings
    op.add_column(
        "face_embeddings",
        sa.Column("embedding_ciphertext", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "face_embeddings",
        sa.Column(
            "key_version",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    # voice_enrollments
    op.add_column(
        "voice_enrollments",
        sa.Column("embedding_ciphertext", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "voice_enrollments",
        sa.Column(
            "key_version",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )


def downgrade() -> None:
    """Drop ciphertext + key_version columns."""
    op.drop_column("voice_enrollments", "key_version")
    op.drop_column("voice_enrollments", "embedding_ciphertext")
    op.drop_column("face_embeddings", "key_version")
    op.drop_column("face_embeddings", "embedding_ciphertext")
