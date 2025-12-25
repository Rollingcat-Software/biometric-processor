"""Async wrapper for face detection operations.

This module provides a non-blocking wrapper around DeepFaceDetector
using the thread pool manager for CPU-bound operations.

Following:
- Decorator Pattern: Wraps existing detector with async behavior
- Open/Closed Principle: Extends behavior without modifying original
- Liskov Substitution: Implements same interface as wrapped detector
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import numpy as np

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.exceptions.face_errors import MLModelTimeoutError
from app.domain.interfaces.face_detector import IFaceDetector
from app.infrastructure.resilience.circuit_breaker import FACE_DETECTOR_BREAKER

if TYPE_CHECKING:
    from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
    from app.infrastructure.ml.detectors.deepface_detector import DeepFaceDetector

logger = logging.getLogger(__name__)


class AsyncFaceDetector:
    """Async wrapper for face detection using thread pool execution.

    This class implements the Decorator Pattern to add non-blocking
    behavior to the existing DeepFaceDetector without modifying it.

    The blocking DeepFace.extract_faces() call is offloaded to a thread
    pool, allowing the async event loop to remain responsive.

    Thread Safety:
        This wrapper is thread-safe. The underlying DeepFaceDetector
        operations are executed in isolated thread pool workers.

    Usage:
        pool = ThreadPoolManager(max_workers=4)
        detector = DeepFaceDetector(detector_backend="opencv")
        async_detector = AsyncFaceDetector(detector, pool)

        # Non-blocking detection:
        result = await async_detector.detect(image)

    Attributes:
        _detector: The wrapped synchronous detector
        _thread_pool: Thread pool manager for async execution
    """

    def __init__(
        self,
        detector: "DeepFaceDetector",
        thread_pool: "ThreadPoolManager",
        timeout_seconds: int = 30,
    ) -> None:
        """Initialize async face detector wrapper.

        Args:
            detector: The synchronous DeepFaceDetector to wrap
            thread_pool: Thread pool manager for executing blocking operations
            timeout_seconds: Timeout for ML operations in seconds (default: 30)

        Note:
            The detector should have a detect_sync method that performs
            the actual blocking detection operation.
        """
        self._detector = detector
        self._thread_pool = thread_pool
        self._timeout_seconds = timeout_seconds

        logger.info(
            f"AsyncFaceDetector initialized wrapping {detector.get_detector_name()} backend "
            f"with {timeout_seconds}s timeout"
        )

    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect face in image asynchronously with timeout and circuit breaker protection.

        This method offloads the blocking DeepFace detection to the
        thread pool, allowing other async operations to proceed.
        Includes timeout protection to prevent indefinite hangs.
        Circuit breaker protects against cascading failures from ML model issues.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            FaceDetectionResult with detection information

        Raises:
            FaceNotDetectedError: When no face is detected
            MultipleFacesError: When multiple faces are detected
            MLModelTimeoutError: When detection exceeds timeout
            CircuitBreakerOpenError: When circuit breaker is open (too many failures)
            RuntimeError: If thread pool has been shut down

        Performance:
            ~10-50ms overhead for thread pool dispatch, but allows
            concurrent request handling during detection.

        Resilience:
            Circuit breaker opens after 5 consecutive failures, preventing
            resource waste on a failing ML model. Auto-recovers after 30s.
        """
        logger.debug(f"Executing face detection in thread pool (timeout: {self._timeout_seconds}s)")

        async def _detect_with_timeout():
            """Inner function to wrap timeout logic for circuit breaker."""
            try:
                # Execute blocking detection in thread pool with timeout
                result = await asyncio.wait_for(
                    self._thread_pool.run_blocking(self._detector.detect_sync, image),
                    timeout=self._timeout_seconds
                )
                return result

            except asyncio.TimeoutError:
                logger.error(
                    f"Face detection timed out after {self._timeout_seconds}s "
                    f"(backend: {self._detector.get_detector_name()})"
                )
                raise MLModelTimeoutError(
                    operation="face_detection",
                    timeout_seconds=self._timeout_seconds
                )

        # Wrap with circuit breaker for resilience
        return await FACE_DETECTOR_BREAKER.call_async(_detect_with_timeout)

    def get_detector_name(self) -> str:
        """Get the name of the underlying detector backend.

        Returns:
            Detector backend name (e.g., "opencv", "retinaface")
        """
        return self._detector.get_detector_name()

    @property
    def detector(self) -> "DeepFaceDetector":
        """Get the wrapped detector instance.

        Useful for accessing detector-specific configuration.
        """
        return self._detector

    def __repr__(self) -> str:
        return (
            f"AsyncFaceDetector(backend={self.get_detector_name()}, "
            f"pool_workers={self._thread_pool.max_workers})"
        )
