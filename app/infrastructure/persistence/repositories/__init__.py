"""Repository implementations for data access."""

from app.infrastructure.persistence.repositories.memory_embedding_repository import (
    InMemoryEmbeddingRepository,
)

__all__ = ["InMemoryEmbeddingRepository"]
