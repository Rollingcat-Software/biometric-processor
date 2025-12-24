"""Caching infrastructure for ML operations.

This module provides caching components to reduce redundant ML computations.
Follows Strategy Pattern with pluggable cache implementations.

Components:
- ThreadSafeLRUCache: Thread-safe LRU cache with TTL support
- CacheStats: Statistics dataclass for cache monitoring
- compute_image_hash: Fast perceptual hashing for images
- compute_embedding_cache_key: Cache key generation for embeddings
- CachedEmbeddingExtractor: Decorator adding caching to extractors
"""

from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache, CacheStats
from app.infrastructure.caching.image_hash import (
    compute_image_hash,
    compute_embedding_cache_key,
    compute_face_region_hash,
)
from app.infrastructure.caching.cached_embedding_extractor import CachedEmbeddingExtractor

__all__ = [
    "ThreadSafeLRUCache",
    "CacheStats",
    "compute_image_hash",
    "compute_embedding_cache_key",
    "compute_face_region_hash",
    "CachedEmbeddingExtractor",
]
