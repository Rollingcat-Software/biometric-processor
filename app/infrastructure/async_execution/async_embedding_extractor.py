"""Async wrapper for embedding extraction operations.

This module provides a non-blocking wrapper around DeepFaceExtractor
using the thread pool manager for CPU-bound operations.

Following:
- Decorator Pattern: Wraps existing extractor with async behavior
- Open/Closed Principle: Extends behavior without modifying original
- Liskov Substitution: Implements same interface as wrapped extractor
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import numpy as np

from app.domain.exceptions.face_errors import MLModelTimeoutError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.infrastructure.resilience.circuit_breaker import EMBEDDING_EXTRACTOR_BREAKER

if TYPE_CHECKING:
    from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
    from app.infrastructure.ml.extractors.deepface_extractor import DeepFaceExtractor

logger = logging.getLogger(__name__)


class AsyncEmbeddingExtractor:
    """Async wrapper for embedding extraction using thread pool execution.

    This class implements the Decorator Pattern to add non-blocking
    behavior to the existing DeepFaceExtractor without modifying it.

    The blocking DeepFace.represent() call is offloaded to a thread
    pool, allowing the async event loop to remain responsive.

    Thread Safety:
        This wrapper is thread-safe. The underlying DeepFaceExtractor
        operations are executed in isolated thread pool workers.

    Usage:
        pool = ThreadPoolManager(max_workers=4)
        extractor = DeepFaceExtractor(model_name="Facenet")
        async_extractor = AsyncEmbeddingExtractor(extractor, pool)

        # Non-blocking extraction:
        embedding = await async_extractor.extract(face_image)

    Attributes:
        _extractor: The wrapped synchronous extractor
        _thread_pool: Thread pool manager for async execution
    """

    def __init__(
        self,
        extractor: "DeepFaceExtractor",
        thread_pool: "ThreadPoolManager",
        timeout_seconds: int = 30,
    ) -> None:
        """Initialize async embedding extractor wrapper.

        Args:
            extractor: The synchronous DeepFaceExtractor to wrap
            thread_pool: Thread pool manager for executing blocking operations
            timeout_seconds: Timeout for ML operations in seconds (default: 30)

        Note:
            The extractor should have an extract_sync method that performs
            the actual blocking extraction operation.
        """
        self._extractor = extractor
        self._thread_pool = thread_pool
        self._timeout_seconds = timeout_seconds

        logger.info(
            f"AsyncEmbeddingExtractor initialized wrapping {extractor.get_model_name()} model "
            f"with {timeout_seconds}s timeout"
        )

    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding asynchronously with timeout and circuit breaker protection.

        This method offloads the blocking DeepFace extraction to the
        thread pool, allowing other async operations to proceed.
        Includes timeout protection to prevent indefinite hangs.
        Circuit breaker protects against cascading failures from ML model issues.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array (dimension depends on model)

        Raises:
            EmbeddingExtractionError: When extraction fails
            MLModelTimeoutError: When extraction exceeds timeout
            CircuitBreakerOpenError: When circuit breaker is open (too many failures)
            RuntimeError: If thread pool has been shut down

        Performance:
            ~10-50ms overhead for thread pool dispatch, but allows
            concurrent request handling during extraction.

        Resilience:
            Circuit breaker opens after 5 consecutive failures, preventing
            resource waste on a failing ML model. Auto-recovers after 30s.
        """
        logger.debug(f"Executing embedding extraction in thread pool (timeout: {self._timeout_seconds}s)")

        async def _extract_with_timeout():
            """Inner function to wrap timeout logic for circuit breaker."""
            try:
                # Execute blocking extraction in thread pool with timeout
                embedding = await asyncio.wait_for(
                    self._thread_pool.run_blocking(self._extractor.extract_sync, face_image),
                    timeout=self._timeout_seconds
                )
                return embedding

            except asyncio.TimeoutError:
                logger.error(
                    f"Embedding extraction timed out after {self._timeout_seconds}s "
                    f"(model: {self._extractor.get_model_name()})"
                )
                raise MLModelTimeoutError(
                    operation="embedding_extraction",
                    timeout_seconds=self._timeout_seconds
                )

        # Wrap with circuit breaker for resilience
        return await EMBEDDING_EXTRACTOR_BREAKER.call_async(_extract_with_timeout)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this extractor.

        Returns:
            Embedding dimension (e.g., 128 for Facenet, 512 for ArcFace)
        """
        return self._extractor.get_embedding_dimension()

    def get_model_name(self) -> str:
        """Get the name of the underlying model.

        Returns:
            Model name (e.g., "Facenet", "ArcFace")
        """
        return self._extractor.get_model_name()

    @property
    def extractor(self) -> "DeepFaceExtractor":
        """Get the wrapped extractor instance.

        Useful for accessing extractor-specific configuration.
        """
        return self._extractor

    def __repr__(self) -> str:
        return (
            f"AsyncEmbeddingExtractor(model={self.get_model_name()}, "
            f"dim={self.get_embedding_dimension()}, "
            f"pool_workers={self._thread_pool.max_workers})"
        )
