"""Cache infrastructure module."""

from app.infrastructure.cache.cached_embedding_repository import (
    CachedEmbeddingRepository,
    CacheEntry,
)

__all__ = ["CachedEmbeddingRepository", "CacheEntry"]
