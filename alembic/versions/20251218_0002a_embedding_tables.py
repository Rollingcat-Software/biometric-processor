"""Create the face_embeddings and voice_enrollments tables.

Revision ID: 0002a_embedding_tables
Revises: 0002_rate_limits_api_keys
Create Date: 2025-12-18

Issue #189. 0001 creates ``biometric_data``, but every later revision and the
runtime repositories (``PgVectorEmbeddingRepository``,
``PgVectorVoiceRepository``) use ``face_embeddings`` and ``voice_enrollments``.
No revision ever created those two tables, so ``alembic upgrade head`` on an
empty database stopped at 0003 (``relation "face_embeddings" does not exist``)
and, past that, at 0005 for ``voice_enrollments``.

This revision is inserted between 0002 and 0003 and creates both tables in the
shape the code expects *before* 0005 runs: 0003 adds indexes on
``face_embeddings`` and 0005 adds ``embedding_ciphertext`` and ``key_version``
to both tables, so those columns are deliberately not created here.

``IF NOT EXISTS`` keeps it a no-op on a database whose tables were created
out of band (the ``scripts/*.sql`` era). A database already stamped at 0003
or later never runs it, because it is an ancestor of that revision.

Column notes (all derived from the SQL the repositories issue):
* ``tenant_id`` is ``VARCHAR``: the repositories compare it with
  ``$n::VARCHAR`` and pass ``None`` in single-tenant mode.
* ``enrollment_type`` holds ``INDIVIDUAL`` rows plus one ``CENTROID`` row per
  user; the partial unique index enforces the single centroid.
* ``deleted_at`` is the soft-delete marker every read filters on.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002a_embedding_tables"
down_revision: Union[str, None] = "0002_rate_limits_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FACE_EMBEDDING_DIMENSION = 512  # Facenet512
VOICE_EMBEDDING_DIMENSION = 256  # Resemblyzer GE2E


def _create_enrollment_table(table: str, dimension: int) -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) NOT NULL,
            tenant_id VARCHAR(255),
            embedding vector({dimension}) NOT NULL,
            quality_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            enrollment_type VARCHAR(50) NOT NULL DEFAULT 'INDIVIDUAL'
                CHECK (enrollment_type IN ('INDIVIDUAL', 'CENTROID')),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_{table}_centroid
        ON {table} (user_id, COALESCE(tenant_id, ''))
        WHERE enrollment_type = 'CENTROID' AND deleted_at IS NULL
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS ix_{table}_user_type_live
        ON {table} (user_id, enrollment_type)
        WHERE deleted_at IS NULL
        """
    )


def upgrade() -> None:
    """Create face_embeddings and voice_enrollments when they do not exist."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _create_enrollment_table("face_embeddings", FACE_EMBEDDING_DIMENSION)
    _create_enrollment_table("voice_enrollments", VOICE_EMBEDDING_DIMENSION)


def downgrade() -> None:
    """Drop both tables. This deletes every stored enrollment."""
    op.execute("DROP TABLE IF EXISTS voice_enrollments")
    op.execute("DROP TABLE IF EXISTS face_embeddings")
