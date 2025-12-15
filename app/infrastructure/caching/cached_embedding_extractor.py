"""Cached embedding extractor decorator.

This module provides a caching layer for embedding extraction operations,
avoiding redundant computation for recently processed images.

Following:
- Decorator Pattern: Wraps existing extractor with caching behavior
- Open/Closed Principle: Extends behavior without modifying original
- Strategy Pattern: Pluggable cache implementation via interface
"""

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np

from app.infrastructure.caching.image_hash import compute_image_hash

if TYPE_CHECKING:
    from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache

logger = logging.getLogger(__name__)


class CachedEmbeddingExtractor:
    """Decorator adding caching to embedding extraction.

    This class implements the Decorator Pattern to add caching behavior
    to any embedding extractor without modifying it. Cache hits avoid
    expensive ML inference operations.

    The cache key is computed from the image content using a fast
    perceptual hash, ensuring that identical images produce the same
    embedding without redundant extraction.

    Thread Safety:
        This wrapper is thread-safe when used with ThreadSafeLRUCache.
        The underlying extractor's thread safety depends on its implementation.

    Usage:
        cache = ThreadSafeLRUCache[str, np.ndarray](max_size=10000, ttl_seconds=3600)
        extractor = DeepFaceExtractor(model_name="Facenet")

        # Add caching layer
        cached_extractor = CachedEmbeddingExtractor(extractor, cache)

        # First call computes embedding
        embedding1 = await cached_extractor.extract(face_image)

        # Second call with same image hits cache (instant)
        embedding2 = await cached_extractor.extract(face_image)

    Attributes:
        _extractor: The wrapped embedding extractor
        _cache: Cache for storing computed embeddings
        _model_name: Name of the embedding model (for cache key namespacing)
    """

    def __init__(
        self,
        extractor,
        cache: "ThreadSafeLRUCache[str, np.ndarray]",
        model_name: Optional[str] = None,
    ) -> None:
        """Initialize cached embedding extractor.

        Args:
            extractor: The embedding extractor to wrap (sync or async)
            cache: Thread-safe cache for storing embeddings
            model_name: Optional model name for cache key namespacing.
                        If not provided, attempts to get from extractor.

        Note:
            Different models produce different embeddings for the same image,
            so cache keys include the model name to prevent collisions.
        """
        self._extractor = extractor
        self._cache = cache
        self._model_name = model_name or self._get_model_name()

        logger.info(
            f"CachedEmbeddingExtractor initialized for model '{self._model_name}' "
            f"with cache max_size={cache.max_size}"
        )

    def _get_model_name(self) -> str:
        """Get model name from extractor if available."""
        if hasattr(self._extractor, "get_model_name"):
            return self._extractor.get_model_name()
        return "unknown"

    def _compute_cache_key(self, image: np.ndarray) -> str:
        """Compute cache key for an image.

        Args:
            image: Face image as numpy array

        Returns:
            Cache key string combining image hash and model name

        Note:
            Model name is included to prevent cross-model cache hits,
            as different models produce different embeddings.
        """
        image_hash = compute_image_hash(image)
        return f"{self._model_name}:{image_hash}"

    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding with caching.

        Checks cache first; on miss, delegates to wrapped extractor
        and stores result in cache.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array

        Raises:
            EmbeddingExtractionError: When extraction fails

        Performance:
            Cache hit: ~0.1ms (hash computation + lookup)
            Cache miss: ~50-200ms (depends on model) + cache overhead
        """
        cache_key = self._compute_cache_key(face_image)

        # Check cache first
        cached_embedding = self._cache.get(cache_key)
        if cached_embedding is not None:
            logger.debug(f"Cache hit for embedding: {cache_key[:20]}...")
            # Return a copy to prevent modification of cached data
            return cached_embedding.copy()

        # Cache miss - extract embedding
        logger.debug(f"Cache miss for embedding: {cache_key[:20]}...")

        # Handle both sync and async extractors
        if hasattr(self._extractor, "extract"):
            result = self._extractor.extract(face_image)
            # Check if result is awaitable (async extractor)
            if hasattr(result, "__await__"):
                embedding = await result
            else:
                embedding = result
        else:
            raise ValueError("Extractor must have an 'extract' method")

        # Store in cache
        self._cache.put(cache_key, embedding.copy())

        return embedding

    def extract_sync(self, face_image: np.ndarray) -> np.ndarray:
        """Synchronous extraction with caching.

        For use when async context is not available.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array
        """
        cache_key = self._compute_cache_key(face_image)

        # Check cache first
        cached_embedding = self._cache.get(cache_key)
        if cached_embedding is not None:
            logger.debug(f"Cache hit for embedding: {cache_key[:20]}...")
            return cached_embedding.copy()

        # Cache miss - extract embedding synchronously
        if hasattr(self._extractor, "extract_sync"):
            embedding = self._extractor.extract_sync(face_image)
        elif hasattr(self._extractor, "extract"):
            # Fallback for sync-only extractors
            embedding = self._extractor.extract(face_image)
        else:
            raise ValueError("Extractor must have 'extract' or 'extract_sync' method")

        # Store in cache
        self._cache.put(cache_key, embedding.copy())

        return embedding

    def invalidate(self, face_image: np.ndarray) -> bool:
        """Invalidate cache entry for a specific image.

        Args:
            face_image: Face image to invalidate

        Returns:
            True if entry was found and removed, False otherwise
        """
        cache_key = self._compute_cache_key(face_image)
        return self._cache.invalidate(cache_key)

    def clear_cache(self) -> None:
        """Clear all cached embeddings."""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache hit/miss statistics
        """
        return self._cache.stats().to_dict()

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this extractor.

        Returns:
            Embedding dimension
        """
        if hasattr(self._extractor, "get_embedding_dimension"):
            return self._extractor.get_embedding_dimension()
        return 128  # Default for unknown

    def get_model_name(self) -> str:
        """Get the name of the underlying model.

        Returns:
            Model name
        """
        return self._model_name

    @property
    def extractor(self):
        """Get the wrapped extractor instance."""
        return self._extractor

    @property
    def cache(self) -> "ThreadSafeLRUCache[str, np.ndarray]":
        """Get the cache instance."""
        return self._cache

    def __repr__(self) -> str:
        stats = self._cache.stats()
        return (
            f"CachedEmbeddingExtractor(model={self._model_name}, "
            f"cache_size={stats.size}/{stats.max_size}, "
            f"hit_rate={stats.hit_rate:.2%})"
        )
