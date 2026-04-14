"""Add client_embedding_observations table (log-only).

Revision ID: 0004_client_embedding_observations
Revises: 0003_performance_indexes
Create Date: 2026-04-14

Stores client-side pre-filter embeddings (128-dim) for offline analysis only.

Design (D1 pre-filter only):
- Log-only table: inserts must not break enrollment/verification flow.
- Client embeddings are NEVER trusted for authentication decisions.
- No HNSW/IVFFlat index — this table is analytical, not searchable at scale.
- Foreign key to server embeddings is nullable and not enforced (soft ref).
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_client_embedding_observations"
down_revision: Union[str, None] = "0003_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create client_embedding_observations table."""

    # Ensure pgvector is available (no-op if already enabled by 0001_initial)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS client_embedding_observations (
            observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) NOT NULL,
            tenant_id UUID,
            session_id VARCHAR(255),
            modality VARCHAR(50) NOT NULL,
            flow VARCHAR(20) NOT NULL,
            client_embedding vector(128),
            client_model_version VARCHAR(100),
            server_embedding_ref UUID NULL,
            cosine_similarity FLOAT8 NULL,
            device_platform VARCHAR(50),
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ceo_user_session
        ON client_embedding_observations (user_id, session_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ceo_created_at
        ON client_embedding_observations (created_at DESC)
        """
    )


def downgrade() -> None:
    """Drop client_embedding_observations table and indexes."""
    op.execute("DROP INDEX IF EXISTS ix_ceo_created_at")
    op.execute("DROP INDEX IF EXISTS ix_ceo_user_session")
    op.execute("DROP TABLE IF EXISTS client_embedding_observations")
