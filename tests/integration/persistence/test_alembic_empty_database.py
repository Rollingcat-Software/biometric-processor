"""``alembic upgrade head`` on an empty pgvector database (issue #189).

The chain is run against a real, empty PostgreSQL + pgvector database, and
the runtime repositories then read and write through every query they issue,
so a column the code uses but no migration creates fails here.

Gated on ``ALEMBIC_TEST_DATABASE_URL`` (for example
``postgresql://test:test@localhost:5432/alembic_db``). The database must be
empty: the fixture refuses to run otherwise and leaves it at ``base`` again
on teardown (which also exercises every ``downgrade()``).
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import numpy as np
import pytest
from cryptography.fernet import Fernet

DATABASE_URL = os.environ.get("ALEMBIC_TEST_DATABASE_URL", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DATABASE_URL,
        reason="ALEMBIC_TEST_DATABASE_URL not set (needs an empty pgvector database)",
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[3]

# Every column the runtime repositories name in their SQL, after head.
ENROLLMENT_COLUMNS = {
    "id",
    "user_id",
    "tenant_id",
    "embedding",
    "embedding_ciphertext",
    "key_version",
    "quality_score",
    "enrollment_type",
    "is_active",
    "created_at",
    "updated_at",
    "deleted_at",
}
OBSERVATION_COLUMNS = {
    "user_id",
    "tenant_id",
    "session_id",
    "modality",
    "flow",
    "client_embedding",
    "client_model_version",
    "server_embedding_ref",
    "device_platform",
    "user_agent",
}


def _alembic_config():
    from alembic.config import Config

    # No ini file: alembic/env.py would call logging.config.fileConfig() and
    # disable the loggers of every module imported before it.
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


async def _fetch(sql: str, *args):
    import asyncpg

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def _user_tables() -> list[str]:
    rows = asyncio.run(
        _fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
        )
    )
    return sorted(row["table_name"] for row in rows)


@pytest.fixture(scope="module")
def migrated_database():
    from alembic import command

    existing = _user_tables()
    if existing:
        pytest.fail(
            f"ALEMBIC_TEST_DATABASE_URL must point at an empty database, found {existing}"
        )

    patcher = pytest.MonkeyPatch()
    patcher.setenv("DATABASE_URL", DATABASE_URL)
    config = _alembic_config()
    command.upgrade(config, "head")
    try:
        yield DATABASE_URL
    finally:
        command.downgrade(config, "base")
        patcher.undo()


@pytest.fixture
def cipher():
    from app.infrastructure.security.embedding_cipher import EmbeddingCipher

    return EmbeddingCipher(Fernet.generate_key())


def _unit_vector(dimension: int, seed: int) -> np.ndarray:
    vector = np.random.default_rng(seed).standard_normal(dimension).astype(np.float32)
    return vector / np.linalg.norm(vector)


async def _columns(table: str) -> dict[str, str]:
    rows = await _fetch(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) AS type "
        "FROM pg_attribute a WHERE a.attrelid = $1::regclass AND a.attnum > 0 AND NOT a.attisdropped",
        table,
    )
    return {row["attname"]: row["type"] for row in rows}


def test_upgrade_WhenDatabaseIsEmpty_ShouldReachTheSingleHead(
    migrated_database: str,
) -> None:
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    rows = asyncio.run(_fetch("SELECT version_num FROM alembic_version"))

    assert [row["version_num"] for row in rows] == [head]


@pytest.mark.parametrize(
    "table, columns, vector_column, vector_type",
    [
        ("face_embeddings", ENROLLMENT_COLUMNS, "embedding", "vector(512)"),
        ("voice_enrollments", ENROLLMENT_COLUMNS, "embedding", "vector(256)"),
        (
            "client_embedding_observations",
            OBSERVATION_COLUMNS,
            "client_embedding",
            "vector(128)",
        ),
    ],
)
def test_schema_WhenUpgradedToHead_ShouldHaveEveryColumnTheRepositoriesUse(
    migrated_database: str,
    table: str,
    columns: set[str],
    vector_column: str,
    vector_type: str,
) -> None:
    actual = asyncio.run(_columns(table))

    assert columns <= set(actual), sorted(columns - set(actual))
    assert actual[vector_column] == vector_type


def test_faceRepository_WhenWritingToMigratedSchema_ShouldServeEveryQuery(
    migrated_database: str, cipher
) -> None:
    from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
        PgVectorEmbeddingRepository,
    )

    async def scenario() -> None:
        repo = PgVectorEmbeddingRepository(
            database_url=migrated_database,
            pool_min_size=1,
            pool_max_size=2,
            cipher=cipher,
        )
        tenant = str(uuid.uuid4())
        probe = _unit_vector(512, seed=1)
        try:
            await repo.save("user-a", probe, quality_score=80.0, tenant_id=tenant)
            await repo.save(
                "user-a",
                _unit_vector(512, seed=2),
                quality_score=70.0,
                tenant_id=tenant,
            )
            await repo.save(
                "user-a",
                probe,
                quality_score=90.0,
                tenant_id=tenant,
                fuse_with_existing=True,
            )
            await repo.bulk_insert(
                [("user-b", tenant, _unit_vector(512, seed=3), 60.0)]
            )

            assert await repo.find_by_user_id("user-a", tenant) is not None
            assert await repo.exists("user-a", tenant)
            assert await repo.count(tenant) >= 4
            assert await repo.find_created_at("user-a", tenant) is not None
            matches = await repo.find_similar(
                probe, threshold=1.0, limit=5, tenant_id=tenant
            )
            assert "user-a" in [user for user, _ in matches]
            assert await repo.search(probe, tenant_id=tenant, limit=5, threshold=0.0)
            assert await repo.get_all_by_tenant(tenant)
            assert await repo.delete("user-a", tenant)
            assert not await repo.exists("user-a", tenant)
        finally:
            await repo.close()

    asyncio.run(scenario())


def test_voiceRepository_WhenWritingToMigratedSchema_ShouldServeEveryQuery(
    migrated_database: str, cipher
) -> None:
    from app.infrastructure.persistence.repositories.pgvector_voice_repository import (
        PgVectorVoiceRepository,
    )

    async def scenario() -> None:
        repo = PgVectorVoiceRepository(database_url=migrated_database, cipher=cipher)
        tenant = str(uuid.uuid4())
        probe = _unit_vector(256, seed=4)
        try:
            await repo.save("voice-a", probe, quality_score=0.9, tenant_id=tenant)
            await repo.save(
                "voice-a",
                probe,
                quality_score=0.8,
                tenant_id=tenant,
                fuse_with_existing=True,
            )

            assert await repo.find_by_user_id("voice-a", tenant) is not None
            assert await repo.exists("voice-a")
            matches = await repo.find_similar(
                probe, threshold=0.4, limit=5, tenant_id=tenant
            )
            assert "voice-a" in [match[0] for match in matches]
            assert await repo.delete_by_user_id("voice-a")
            assert not await repo.exists("voice-a")
        finally:
            await repo.close()

    asyncio.run(scenario())


def test_observationRepository_WhenRecordingToMigratedSchema_ShouldStoreTheRow(
    migrated_database: str,
) -> None:
    from app.infrastructure.persistence.client_embedding_observation_repository import (
        ClientEmbeddingObservationRepository,
    )

    async def scenario() -> int:
        repo = ClientEmbeddingObservationRepository(database_url=migrated_database)
        try:
            await repo.record(
                user_id="observed-user",
                tenant_id=str(uuid.uuid4()),
                session_id="session-1",
                modality="face",
                flow="enroll",
                client_embedding_json=json.dumps(_unit_vector(128, seed=5).tolist()),
                client_model_version="test",
                device_platform="web",
                user_agent="pytest",
            )
        finally:
            await repo.close()
        rows = await _fetch(
            "SELECT count(*) AS n FROM client_embedding_observations WHERE user_id = 'observed-user'"
        )
        return rows[0]["n"]

    assert asyncio.run(scenario()) == 1
