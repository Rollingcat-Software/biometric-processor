"""The alembic chain against databases that already hold data (issue #189).

``test_alembic_empty_database.py`` covers the empty database. This module
covers the cases where ``0002a_embedding_tables`` meets tables it did not
create and where a downgrade would destroy stored enrollments:

* tables already in the shape 0002a builds are kept, rows included;
* a ``face_embeddings`` table from the pre-alembic ``scripts/init-db.sql``
  stops the upgrade with a message naming the missing columns, instead of a
  bare SQL error from a later index statement;
* a downgrade past 0002a refuses while either enrollment table holds rows;
* ``alembic check`` (autogenerate) refuses, because the declarative models do
  not describe the migrated schema.

Each test runs in its own scratch database created next to the one named by
``ALEMBIC_TEST_DATABASE_URL`` (the role must be allowed to create databases;
the CI service user is a superuser) and dropped afterwards.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

DATABASE_URL = os.environ.get("ALEMBIC_TEST_DATABASE_URL", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DATABASE_URL,
        reason="ALEMBIC_TEST_DATABASE_URL not set (needs a pgvector server)",
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[3]
BEFORE_EMBEDDING_TABLES = "0002_rate_limits_api_keys"

# face_embeddings exactly as scripts/init-db.sql creates it (pre-alembic era).
LEGACY_FACE_EMBEDDINGS = """
CREATE TABLE face_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255),
    embedding vector(512) NOT NULL,
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0 AND quality_score <= 100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT unique_user_tenant UNIQUE (user_id, tenant_id)
)
"""


def _current_shape(table: str, dimension: int) -> str:
    return f"""
    CREATE TABLE {table} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR(255) NOT NULL,
        tenant_id VARCHAR(255),
        embedding vector({dimension}) NOT NULL,
        quality_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        enrollment_type VARCHAR(50) NOT NULL DEFAULT 'INDIVIDUAL',
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        deleted_at TIMESTAMPTZ
    )
    """


def _vector_literal(dimension: int) -> str:
    return "[" + ",".join(["0.1"] * dimension) + "]"


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


async def _execute(url: str, *statements: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(url)
    try:
        for statement in statements:
            await conn.execute(statement)
    finally:
        await conn.close()


async def _fetchval(url: str, sql: str):
    import asyncpg

    conn = await asyncpg.connect(url)
    try:
        return await conn.fetchval(sql)
    finally:
        await conn.close()


def _alembic_config():
    from alembic.config import Config

    # No ini file: alembic/env.py would call logging.config.fileConfig() and
    # disable the loggers of every module imported before it.
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


@pytest.fixture
def scratch_database(monkeypatch: pytest.MonkeyPatch):
    """A new, empty database on the test server; ``DATABASE_URL`` points at it."""
    name = f"alembic_scratch_{uuid.uuid4().hex[:12]}"
    asyncio.run(_execute(DATABASE_URL, f'CREATE DATABASE "{name}"'))
    url = _with_database(DATABASE_URL, name)
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        yield url
    finally:
        asyncio.run(
            _execute(DATABASE_URL, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        )


def test_upgrade_WhenEnrollmentTablesAlreadyHaveCurrentShape_ShouldKeepRowsAndReachHead(
    scratch_database: str,
) -> None:
    from alembic import command

    asyncio.run(
        _execute(
            scratch_database,
            "CREATE EXTENSION IF NOT EXISTS vector",
            _current_shape("face_embeddings", 512),
            _current_shape("voice_enrollments", 256),
            "INSERT INTO face_embeddings (user_id, embedding) "
            f"VALUES ('kept', '{_vector_literal(512)}')",
        )
    )

    command.upgrade(_alembic_config(), "head")

    assert (
        asyncio.run(
            _fetchval(
                scratch_database,
                "SELECT count(*) FROM face_embeddings WHERE user_id = 'kept'",
            )
        )
        == 1
    )


def test_upgrade_WhenFaceEmbeddingsComeFromLegacyInitScript_ShouldStopNamingMissingColumns(
    scratch_database: str,
) -> None:
    from alembic import command

    asyncio.run(
        _execute(
            scratch_database,
            "CREATE EXTENSION IF NOT EXISTS vector",
            LEGACY_FACE_EMBEDDINGS,
        )
    )

    with pytest.raises(Exception) as raised:
        command.upgrade(_alembic_config(), "head")

    message = str(raised.value)
    assert "face_embeddings" in message
    assert "enrollment_type" in message
    assert "is_active" in message
    # The whole upgrade ran in one transaction, so nothing was stamped.
    assert (
        asyncio.run(
            _fetchval(scratch_database, "SELECT to_regclass('public.alembic_version')")
        )
        is None
    )


def test_downgrade_WhenEnrollmentsAreStored_ShouldRefuseAndKeepRows(
    scratch_database: str,
) -> None:
    from alembic import command

    config = _alembic_config()
    command.upgrade(config, "head")
    asyncio.run(
        _execute(
            scratch_database,
            "INSERT INTO voice_enrollments (user_id, embedding) "
            f"VALUES ('kept', '{_vector_literal(256)}')",
        )
    )

    with pytest.raises(Exception, match="voice_enrollments"):
        command.downgrade(config, BEFORE_EMBEDDING_TABLES)

    assert (
        asyncio.run(
            _fetchval(scratch_database, "SELECT count(*) FROM voice_enrollments")
        )
        == 1
    )


def test_downgrade_WhenEnrollmentTablesAreEmpty_ShouldDropThem(
    scratch_database: str,
) -> None:
    from alembic import command

    config = _alembic_config()
    command.upgrade(config, "head")

    command.downgrade(config, BEFORE_EMBEDDING_TABLES)

    assert (
        asyncio.run(
            _fetchval(
                scratch_database,
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name IN ('face_embeddings', 'voice_enrollments')",
            )
        )
        == 0
    )


def test_check_WhenAutogenerateRequested_ShouldRefuseBecauseModelsDoNotDescribeSchema(
    scratch_database: str,
) -> None:
    from alembic import command
    from alembic.util import CommandError

    config = _alembic_config()
    command.upgrade(config, "head")

    with pytest.raises(CommandError, match="does not provide a MetaData object"):
        command.check(config)
