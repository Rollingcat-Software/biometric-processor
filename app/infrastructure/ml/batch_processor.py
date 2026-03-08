"""Batch inference processor for efficient ML operations.

Provides a batching layer that collects individual inference requests
and processes them together for improved GPU utilization and throughput.

Benefits of batching:
- Better GPU utilization through parallel processing
- Reduced per-request overhead (model loading, memory transfers)
- Higher throughput for concurrent requests
- Lower average latency under load
"""

import asyncio
import logging
import time
from typing import List, Callable, Awaitable, TypeVar, Generic, Optional
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager

import numpy as np
from prometheus_client import Histogram, Counter, Gauge

logger = logging.getLogger(__name__)

# Type variables for generic batch processor
T = TypeVar("T")  # Input type
R = TypeVar("R")  # Result type

# =============================================================================
# Prometheus Metrics
# =============================================================================

batch_size_histogram = Histogram(
    "biometric_batch_size",
    "Actual batch sizes processed",
    ["processor_name"],
    buckets=[1, 2, 4, 8, 16, 32],
)

batch_latency_histogram = Histogram(
    "biometric_batch_latency_seconds",
    "Batch processing latency",
    ["processor_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

batch_wait_histogram = Histogram(
    "biometric_batch_wait_seconds",
    "Time requests wait before batch processing",
    ["processor_name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
)

batch_requests_total = Counter(
    "biometric_batch_requests_total",
    "Total batch requests processed",
    ["processor_name"],
)

batch_queue_size = Gauge(
    "biometric_batch_queue_size",
    "Current batch queue size",
    ["processor_name"],
)


# =============================================================================
# Batch Request Container
# =============================================================================


@dataclass
class BatchRequest(Generic[T]):
    """A request waiting for batch processing.

    Attributes:
        data: The input data for processing
        future: Asyncio future to receive the result
        timestamp: When the request was submitted
    """

    data: T
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# Batch Inference Processor
# =============================================================================


class BatchInferenceProcessor(Generic[T, R]):
    """Batches multiple inference requests for efficient processing.

    When multiple requests arrive within the batch window:
    1. Requests are queued with their futures
    2. When batch is full OR timeout occurs, process batch together
    3. Results are distributed to waiting callers via futures

    Example usage:
        async def process_batch(images: List[np.ndarray]) -> List[np.ndarray]:
            # Stack images and run through model
            batch = np.stack(images)
            return model.predict(batch)

        processor = BatchInferenceProcessor(
            process_batch=process_batch,
            max_batch_size=8,
            max_wait_time=0.1
        )

        await processor.start()

        # Individual requests are automatically batched
        result = await processor.process(image)
    """

    def __init__(
        self,
        process_batch: Callable[[List[T]], Awaitable[List[R]]],
        max_batch_size: int = 8,
        max_wait_time: float = 0.1,  # 100ms
        name: str = "batch_processor",
    ):
        """Initialize batch processor.

        Args:
            process_batch: Async function that processes a batch of inputs
            max_batch_size: Maximum number of items in a batch
            max_wait_time: Maximum time to wait for batch to fill (seconds)
            name: Name for metrics and logging
        """
        self.process_batch = process_batch
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.name = name

        self._queue: deque[BatchRequest[T]] = deque()
        self._lock = asyncio.Lock()
        self._processing = False
        self._running = False
        self._background_task: Optional[asyncio.Task] = None

        # Statistics
        self._total_requests = 0
        self._total_batches = 0

    async def start(self):
        """Start the background batch processor."""
        if self._running:
            return

        self._running = True
        self._background_task = asyncio.create_task(self._background_processor())
        logger.info(
            f"BatchInferenceProcessor '{self.name}' started "
            f"(max_batch={self.max_batch_size}, max_wait={self.max_wait_time}s)"
        )

    async def stop(self):
        """Stop the background batch processor."""
        if not self._running:
            return

        self._running = False

        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

        # Process any remaining requests
        async with self._lock:
            while self._queue:
                await self._process_batch()

        logger.info(f"BatchInferenceProcessor '{self.name}' stopped")

    async def process(self, data: T, timeout: float = 10.0) -> R:
        """Submit data for batch processing.

        Args:
            data: Input data to process
            timeout: Maximum time to wait for result (seconds)

        Returns:
            Processing result

        Raises:
            RuntimeError: If processing times out or fails
            asyncio.CancelledError: If request is cancelled
        """
        if not self._running:
            raise RuntimeError(f"BatchInferenceProcessor '{self.name}' is not running")

        # Create request with future
        loop = asyncio.get_event_loop()
        request = BatchRequest(data=data, future=loop.create_future())

        async with self._lock:
            self._queue.append(request)
            batch_queue_size.labels(processor_name=self.name).set(len(self._queue))

            # If batch is full, process immediately
            if len(self._queue) >= self.max_batch_size:
                await self._process_batch()

        # Wait for result
        try:
            return await asyncio.wait_for(request.future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Batch processing timeout for '{self.name}'")
            raise RuntimeError(f"Batch processing timeout for '{self.name}'")

    async def _background_processor(self):
        """Background task that processes batches on timeout."""
        while self._running:
            try:
                await asyncio.sleep(self.max_wait_time)

                async with self._lock:
                    if self._queue and not self._processing:
                        await self._process_batch()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background processor error: {e}")

    async def _process_batch(self):
        """Process all queued requests as a batch."""
        if self._processing or not self._queue:
            return

        self._processing = True
        batch_start_time = time.time()

        try:
            # Collect batch
            batch_requests: List[BatchRequest[T]] = []
            while self._queue and len(batch_requests) < self.max_batch_size:
                batch_requests.append(self._queue.popleft())

            if not batch_requests:
                return

            batch_queue_size.labels(processor_name=self.name).set(len(self._queue))

            # Record wait times
            for req in batch_requests:
                wait_time = batch_start_time - req.timestamp
                batch_wait_histogram.labels(processor_name=self.name).observe(wait_time)

            # Extract data
            batch_data = [req.data for req in batch_requests]
            batch_size = len(batch_data)

            # Record batch size
            batch_size_histogram.labels(processor_name=self.name).observe(batch_size)

            logger.debug(f"Processing batch of {batch_size} items")

            # Process batch
            try:
                results = await self.process_batch(batch_data)

                # Distribute results
                for request, result in zip(batch_requests, results):
                    if not request.future.done():
                        request.future.set_result(result)

                self._total_requests += batch_size
                self._total_batches += 1
                batch_requests_total.labels(processor_name=self.name).inc(batch_size)

            except Exception as e:
                # Propagate error to all waiting requests
                logger.error(f"Batch processing failed: {e}")
                for request in batch_requests:
                    if not request.future.done():
                        request.future.set_exception(e)

        finally:
            self._processing = False

            # Record latency
            latency = time.time() - batch_start_time
            batch_latency_histogram.labels(processor_name=self.name).observe(latency)

    def stats(self) -> dict:
        """Get processor statistics.

        Returns:
            Dictionary with processor statistics
        """
        return {
            "name": self.name,
            "queue_size": len(self._queue),
            "max_batch_size": self.max_batch_size,
            "max_wait_time": self.max_wait_time,
            "processing": self._processing,
            "running": self._running,
            "total_requests": self._total_requests,
            "total_batches": self._total_batches,
            "avg_batch_size": (
                self._total_requests / self._total_batches
                if self._total_batches > 0
                else 0
            ),
        }


# =============================================================================
# Batch Embedding Extractor
# =============================================================================


class BatchEmbeddingExtractor:
    """Batch-optimized face embedding extractor.

    Wraps an ML model with batch processing for improved throughput
    when handling concurrent requests.

    Usage:
        extractor = BatchEmbeddingExtractor(model, max_batch_size=8)
        await extractor.start()

        # Individual requests are batched automatically
        embedding = await extractor.extract(face_image)

        await extractor.stop()
    """

    def __init__(
        self,
        model,
        max_batch_size: int = 8,
        max_wait_time: float = 0.1,
        name: str = "embedding_extractor",
    ):
        """Initialize batch embedding extractor.

        Args:
            model: ML model with predict() method
            max_batch_size: Maximum batch size
            max_wait_time: Maximum wait time for batching (seconds)
            name: Name for metrics
        """
        self.model = model
        self.processor = BatchInferenceProcessor(
            process_batch=self._extract_batch,
            max_batch_size=max_batch_size,
            max_wait_time=max_wait_time,
            name=name,
        )

    async def start(self):
        """Start the batch processor."""
        await self.processor.start()

    async def stop(self):
        """Stop the batch processor."""
        await self.processor.stop()

    async def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract embedding for single image (batched internally).

        Args:
            image: Face image as numpy array

        Returns:
            Embedding vector as numpy array
        """
        return await self.processor.process(image)

    async def _extract_batch(self, images: List[np.ndarray]) -> List[np.ndarray]:
        """Process a batch of images.

        Args:
            images: List of face images

        Returns:
            List of embedding vectors
        """
        # Stack images into batch
        batch = np.stack(images, axis=0)

        # Run model inference (single call for entire batch)
        # This works with TensorFlow, PyTorch, and ONNX models
        if hasattr(self.model, "predict"):
            embeddings = self.model.predict(batch)
        elif hasattr(self.model, "__call__"):
            embeddings = self.model(batch)
        else:
            raise ValueError("Model must have predict() or __call__() method")

        # Split back into list
        return [embeddings[i] for i in range(len(images))]

    def stats(self) -> dict:
        """Get processor statistics."""
        return self.processor.stats()

    @asynccontextmanager
    async def batch_context(self):
        """Context manager for automatic start/stop.

        Usage:
            async with extractor.batch_context():
                embedding = await extractor.extract(image)
        """
        await self.start()
        try:
            yield self
        finally:
            await self.stop()


# =============================================================================
# Adaptive Batch Processor
# =============================================================================


class AdaptiveBatchProcessor(BatchInferenceProcessor[T, R]):
    """Batch processor with adaptive batch size.

    Automatically adjusts batch size based on:
    - Current queue pressure
    - Processing latency
    - Memory constraints

    This helps maintain consistent latency while maximizing throughput.
    """

    def __init__(
        self,
        process_batch: Callable[[List[T]], Awaitable[List[R]]],
        min_batch_size: int = 1,
        max_batch_size: int = 32,
        target_latency: float = 0.1,  # 100ms target
        name: str = "adaptive_batch_processor",
    ):
        """Initialize adaptive batch processor.

        Args:
            process_batch: Async function that processes a batch
            min_batch_size: Minimum batch size
            max_batch_size: Maximum batch size
            target_latency: Target processing latency (seconds)
            name: Name for metrics
        """
        super().__init__(
            process_batch=process_batch,
            max_batch_size=max_batch_size,
            max_wait_time=target_latency / 2,  # Wait half the target
            name=name,
        )
        self.min_batch_size = min_batch_size
        self.target_latency = target_latency
        self._current_batch_size = min_batch_size
        self._recent_latencies: deque[float] = deque(maxlen=10)

    async def _process_batch(self):
        """Process batch with adaptive sizing."""
        start_time = time.time()
        await super()._process_batch()
        latency = time.time() - start_time

        # Update latency history
        self._recent_latencies.append(latency)

        # Adjust batch size based on latency
        if len(self._recent_latencies) >= 3:
            avg_latency = sum(self._recent_latencies) / len(self._recent_latencies)

            if avg_latency < self.target_latency * 0.8:
                # Under target, can increase batch size
                self._current_batch_size = min(
                    self._current_batch_size + 1, self.max_batch_size
                )
            elif avg_latency > self.target_latency * 1.2:
                # Over target, decrease batch size
                self._current_batch_size = max(
                    self._current_batch_size - 1, self.min_batch_size
                )

            # Update effective max batch size
            self.max_batch_size = self._current_batch_size

    def stats(self) -> dict:
        """Get processor statistics including adaptive metrics."""
        base_stats = super().stats()
        base_stats.update(
            {
                "current_batch_size": self._current_batch_size,
                "min_batch_size": self.min_batch_size,
                "target_latency": self.target_latency,
                "recent_avg_latency": (
                    sum(self._recent_latencies) / len(self._recent_latencies)
                    if self._recent_latencies
                    else 0
                ),
            }
        )
        return base_stats
