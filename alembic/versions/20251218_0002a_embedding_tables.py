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

Databases that already have the tables (created out of band, the
``scripts/*.sql`` era) are handled as follows:

* a table that already has every column listed in ``REQUIRED_COLUMNS`` is
  kept as it is, rows included (``IF NOT EXISTS``);
* a table that lacks any of them (for example ``face_embeddings`` from
  ``scripts/init-db.sql``, which has no ``enrollment_type`` or ``is_active``,
  or the 128-dimension table from ``scripts/init-database.sql``) stops the
  upgrade with an error naming the missing columns. Such a table also needs
  constraint and data decisions (``init-db.sql`` has ``UNIQUE (user_id,
  tenant_id)``, which forbids the per-user centroid row), so it is reconciled
  by hand, not guessed at here.

A database already stamped at 0003 or later never runs this revision, because
it is an ancestor of that revision.

``downgrade()`` drops the two tables only while both are empty. With stored
enrollments it refuses: this revision cannot tell whether it created the
tables or found them, and dropping them would delete every enrollment.

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
ENROLLMENT_TABLES = ("face_embeddings", "voice_enrollments")

# Columns created below; an existing table must already have all of them.
REQUIRED_COLUMNS = (
    "id",
    "user_id",
    "tenant_id",
    "embedding",
    "quality_score",
    "enrollment_type",
    "is_active",
    "created_at",
    "updated_at",
    "deleted_at",
)


def _require_current_shape(table: str) -> None:
    """Stop the upgrade when ``table`` exists without the expected columns."""
    required = ", ".join(f"'{column}'" for column in REQUIRED_COLUMNS)
    op.execute(
        f"""
        DO $$
        DECLARE
            missing TEXT;
        BEGIN
            IF to_regclass('{table}') IS NULL THEN
                RETURN;
            END IF;
            SELECT string_agg(required.column_name, ', ' ORDER BY required.column_name)
              INTO missing
              FROM unnest(ARRAY[{required}]) AS required(column_name)
             WHERE NOT EXISTS (
                   SELECT 1 FROM information_schema.columns c
                    WHERE c.table_schema = current_schema()
                      AND c.table_name = '{table}'
                      AND c.column_name = required.column_name);
            IF missing IS NOT NULL THEN
                RAISE EXCEPTION
                    'Table {table} already exists without column(s) %. It predates '
                    'the alembic chain; reconcile it by hand (see revision '
                    '0002a_embedding_tables) and run the upgrade again.', missing;
            END IF;
        END
        $$
        """
    )


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
    for table in ENROLLMENT_TABLES:
        _require_current_shape(table)
    _create_enrollment_table("face_embeddings", FACE_EMBEDDING_DIMENSION)
    _create_enrollment_table("voice_enrollments", VOICE_EMBEDDING_DIMENSION)


def downgrade() -> None:
    """Drop both tables, but only while neither holds a row.

    Raises (and the whole downgrade rolls back) when either table stores an
    enrollment. To go below this revision on purpose, back the tables up,
    drop or empty them by hand, then downgrade.
    """
    op.execute(
        """
        DO $$
        DECLARE
            name TEXT;
            stored BOOLEAN;
        BEGIN
            FOREACH name IN ARRAY ARRAY['face_embeddings', 'voice_enrollments'] LOOP
                IF to_regclass(name) IS NOT NULL THEN
                    EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I)', name) INTO stored;
                    IF stored THEN
                        RAISE EXCEPTION
                            'Refusing to drop % while it stores enrollments. Back it '
                            'up, drop or empty it by hand, then downgrade again.', name;
                    END IF;
                END IF;
            END LOOP;
        END
        $$
        """
    )
    op.execute("DROP TABLE IF EXISTS voice_enrollments")
    op.execute("DROP TABLE IF EXISTS face_embeddings")
