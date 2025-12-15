"""Async execution infrastructure for CPU-bound ML operations.

This module provides non-blocking wrappers for synchronous ML operations
using thread pool executors. Follows Decorator Pattern for transparent
async behavior addition.

Components:
- ThreadPoolManager: Centralized thread pool singleton
- AsyncFaceDetector: Non-blocking face detection wrapper
- AsyncEmbeddingExtractor: Non-blocking embedding extraction wrapper
"""

from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager
from app.infrastructure.async_execution.async_face_detector import AsyncFaceDetector
from app.infrastructure.async_execution.async_embedding_extractor import AsyncEmbeddingExtractor

__all__ = [
    "ThreadPoolManager",
    "AsyncFaceDetector",
    "AsyncEmbeddingExtractor",
]
