"""Factory for creating embedding extractors.

Supports both synchronous and asynchronous extractor creation with
optional caching and thread pool execution.

Following:
- Factory Pattern: Centralized extractor creation
- Open/Closed: New extractors without modifying existing code
- Decorator Pattern: Async/cache wrappers add behavior without modification
"""

import logging
from typing import Optional, TYPE_CHECKING

from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.infrastructure.ml.extractors.deepface_extractor import DeepFaceExtractor

if TYPE_CHECKING:
    from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
    from app.infrastructure.caching.lru_cache import ThreadSafeLRUCache
    import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingExtractorFactory:
    """Factory for creating embedding extractor instances.

    Implements Factory Pattern for creating different embedding extractor implementations.
    This allows adding new extractors without modifying client code (Open/Closed Principle).

    Supported Models:
    - VGG-Face: 2622-D, older but reliable
    - Facenet: 128-D, good balance (recommended)
    - Facenet512: 512-D, higher accuracy
    - OpenFace: 128-D, fast
    - DeepFace: 4096-D, Facebook's model
    - DeepID: 160-D
    - ArcFace: 512-D, state-of-the-art
    - Dlib: 128-D
    - SFace: 128-D

    Async Support:
        When async_enabled=True and thread_pool is provided, returns an
        AsyncEmbeddingExtractor wrapper for non-blocking extraction.

    Caching Support:
        When cache_enabled=True and cache is provided, wraps with
        CachedEmbeddingExtractor for caching embeddings by image hash.
    """

    @staticmethod
    def create(
        model_name: str = "Facenet",
        async_enabled: bool = False,
        cache_enabled: bool = False,
        thread_pool: Optional["ThreadPoolManager"] = None,
        cache: Optional["ThreadSafeLRUCache[str, np.ndarray]"] = None,
        **kwargs,
    ) -> IEmbeddingExtractor:
        """Create an embedding extractor instance.

        Args:
            model_name: Model name to use for extraction
                Options: "VGG-Face", "Facenet", "Facenet512", "OpenFace",
                        "DeepFace", "DeepID", "ArcFace", "Dlib", "SFace"
            async_enabled: If True, wrap with AsyncEmbeddingExtractor
            cache_enabled: If True, wrap with CachedEmbeddingExtractor
            thread_pool: Thread pool manager for async execution
            cache: LRU cache for embedding caching
            **kwargs: Additional arguments passed to extractor constructor

        Returns:
            Embedding extractor instance implementing IEmbeddingExtractor
            May be wrapped with async and/or caching decorators

        Raises:
            ValueError: If model_name is not supported
            ValueError: If async_enabled but thread_pool is None
            ValueError: If cache_enabled but cache is None

        Example:
            ```python
            # Basic synchronous extractor
            extractor = EmbeddingExtractorFactory.create("Facenet")

            # Async extractor with caching
            pool = ThreadPoolManager(max_workers=4)
            cache = ThreadSafeLRUCache(max_size=10000)
            extractor = EmbeddingExtractorFactory.create(
                "Facenet",
                async_enabled=True,
                cache_enabled=True,
                thread_pool=pool,
                cache=cache
            )
            ```

        Note:
            Wrapping order: base -> async -> cache
            This ensures cache checks happen before async dispatch.
        """
        logger.info(
            f"Creating embedding extractor: {model_name} "
            f"(async={async_enabled}, cache={cache_enabled})"
        )

        supported_models = [
            "VGG-Face",
            "Facenet",
            "Facenet512",
            "OpenFace",
            "DeepFace",
            "DeepID",
            "ArcFace",
            "Dlib",
            "SFace",
        ]

        if model_name not in supported_models:
            raise ValueError(
                f"Unsupported model: {model_name}. "
                f"Supported models: {', '.join(supported_models)}"
            )

        # Create base extractor
        extractor = DeepFaceExtractor(model_name=model_name, **kwargs)

        # Wrap with async if requested (do this first)
        if async_enabled:
            if thread_pool is None:
                raise ValueError(
                    "thread_pool is required when async_enabled=True"
                )
            from app.infrastructure.async_execution.async_embedding_extractor import (
                AsyncEmbeddingExtractor,
            )
            extractor = AsyncEmbeddingExtractor(extractor, thread_pool)

        # Wrap with cache if requested (do this last so cache is checked first)
        if cache_enabled:
            if cache is None:
                raise ValueError(
                    "cache is required when cache_enabled=True"
                )
            from app.infrastructure.caching.cached_embedding_extractor import (
                CachedEmbeddingExtractor,
            )
            extractor = CachedEmbeddingExtractor(extractor, cache, model_name)

        return extractor

    @staticmethod
    def get_available_models() -> list[str]:
        """Get list of available model names.

        Returns:
            List of supported model names
        """
        return [
            "VGG-Face",
            "Facenet",
            "Facenet512",
            "OpenFace",
            "DeepFace",
            "DeepID",
            "ArcFace",
            "Dlib",
            "SFace",
        ]

    @staticmethod
    def get_recommended_model() -> str:
        """Get recommended model for production use.

        Returns:
            Recommended model name
        """
        return "Facenet"  # Good balance of accuracy and performance

    @staticmethod
    def get_model_dimension(model_name: str) -> int:
        """Get embedding dimension for a model.

        Args:
            model_name: Model name

        Returns:
            Embedding dimension

        Raises:
            ValueError: If model_name is not supported
        """
        dimensions = {
            "VGG-Face": 2622,
            "Facenet": 128,
            "Facenet512": 512,
            "OpenFace": 128,
            "DeepFace": 4096,
            "DeepID": 160,
            "ArcFace": 512,
            "Dlib": 128,
            "SFace": 128,
        }

        if model_name not in dimensions:
            raise ValueError(f"Unknown model: {model_name}")

        return dimensions[model_name]
