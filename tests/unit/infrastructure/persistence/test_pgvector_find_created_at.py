"""Unit tests for PgVectorEmbeddingRepository.find_created_at.

The method feeds the adaptive (aged-embedding) verification threshold, so it
must return a naive UTC datetime and must not depend on third-party timezone
packages that are not declared in requirements.txt.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
    PgVectorEmbeddingRepository,
)


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _repository_returning(created_at):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={"created_at": created_at})
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireContext(conn))
    repository = PgVectorEmbeddingRepository(
        database_url="postgresql://unused/unused", cipher=MagicMock()
    )
    repository._ensure_pool = AsyncMock(return_value=pool)
    return repository


async def test_findCreatedAt_WhenRowIsTimezoneAware_ShouldReturnNaiveUtc():
    istanbul = timezone(timedelta(hours=3))
    stored = datetime(2026, 11, 3, 1, 17, 49, tzinfo=istanbul)
    repository = _repository_returning(stored)

    created_at = await repository.find_created_at("user-1", "tenant-1")

    assert created_at == datetime(2026, 11, 2, 22, 17, 49)
    assert created_at.tzinfo is None


async def test_findCreatedAt_WhenRowIsNaive_ShouldReturnItUnchanged():
    stored = datetime(2026, 11, 2, 22, 17, 49)
    repository = _repository_returning(stored)

    created_at = await repository.find_created_at("user-1", "tenant-1")

    assert created_at == stored
