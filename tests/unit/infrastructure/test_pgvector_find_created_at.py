"""``PgVectorEmbeddingRepository.find_created_at`` (found while fixing #189).

asyncpg returns ``timestamptz`` as an aware datetime. The method converted it
with ``pytz``, which is not a dependency (pandas 3 dropped it), so the import
raised, the broad ``except`` logged it, and the method returned ``None`` for
every enrolled user.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from cryptography.fernet import Fernet

from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
    PgVectorEmbeddingRepository,
)
from app.infrastructure.security.embedding_cipher import EmbeddingCipher


def _repository_returning(created_at: datetime) -> PgVectorEmbeddingRepository:
    repo = PgVectorEmbeddingRepository(
        database_url="postgresql://unused/unused",
        cipher=EmbeddingCipher(Fernet.generate_key()),
    )
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={"created_at": created_at})

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    repo._pool = pool
    return repo


async def test_findCreatedAt_WhenRowHasAwareTimestamp_ShouldReturnNaiveUtc() -> None:
    istanbul = timezone(timedelta(hours=3))
    repo = _repository_returning(datetime(2026, 11, 9, 12, 30, tzinfo=istanbul))

    created_at = await repo.find_created_at("user-a", "tenant-a")

    assert created_at == datetime(2026, 11, 9, 9, 30)
    assert created_at.tzinfo is None
