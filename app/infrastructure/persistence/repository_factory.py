"""Embedding repository factory."""

import logging
from typing import Literal, Optional

from app.domain.interfaces.embedding_repository import IEmbeddingRepository

logger = logging.getLogger(__name__)

RepositoryBackend = Literal["memory", "postgres"]


class EmbeddingRepositoryFactory:
    """Factory for creating embedding repository instances.

    Follows Open/Closed Principle: Add new backends without modifying existing code.
    """

    @staticmethod
    def create(
        backend: RepositoryBackend = "memory",
        database_url: Optional[str] = None,
        embedding_dimension: int = 512,
        pool_size: int = 10,
    ) -> IEmbeddingRepository:
        """Create embedding repository instance.

        Args:
            backend: Repository backend type
            database_url: Database URL (required for postgres)
            embedding_dimension: Dimension of embedding vectors
            pool_size: Connection pool size (postgres only)

        Returns:
            IEmbeddingRepository implementation

        Raises:
            ValueError: If unknown backend or missing required params
        """
        if backend == "memory":
            from app.infrastructure.persistence.repositories.memory_embedding_repository import (
                InMemoryEmbeddingRepository,
            )

            logger.info("Creating InMemoryEmbeddingRepository")
            return InMemoryEmbeddingRepository()

        elif backend == "postgres":
            if not database_url:
                raise ValueError("database_url is required for postgres backend")

            from app.infrastructure.persistence.repositories.postgres_embedding_repository import (
                PostgresEmbeddingRepository,
            )

            logger.info(
                f"Creating PostgresEmbeddingRepository (dim={embedding_dimension})"
            )
            return PostgresEmbeddingRepository(
                database_url=database_url,
                embedding_dimension=embedding_dimension,
                pool_size=pool_size,
            )

        raise ValueError(f"Unknown repository backend: {backend}")
