"""Factory for creating face detectors.

Supports both synchronous and asynchronous detector creation with
optional thread pool execution for non-blocking detection.

Following:
- Factory Pattern: Centralized detector creation
- Open/Closed: New detectors without modifying existing code
- Decorator Pattern: Async wrappers add behavior without modification
"""

import logging
from typing import Optional, TYPE_CHECKING

from app.domain.interfaces.face_detector import IFaceDetector
from app.infrastructure.ml.detectors.deepface_detector import DeepFaceDetector

if TYPE_CHECKING:
    from app.infrastructure.async_execution.thread_pool_manager import ThreadPoolManager

logger = logging.getLogger(__name__)


class FaceDetectorFactory:
    """Factory for creating face detector instances.

    Implements Factory Pattern for creating different face detector implementations.
    This allows adding new detectors without modifying client code (Open/Closed Principle).

    Supported Detectors:
    - opencv: Fast but less accurate
    - ssd: Single Shot Detector
    - mtcnn: Multi-task CNN (good balance)
    - retinaface: Most accurate
    - mediapipe: Google's MediaPipe
    - yolov8: YOLO v8 detector

    Async Support:
        When async_enabled=True and thread_pool is provided, returns an
        AsyncFaceDetector wrapper that executes detection in a thread pool.
    """

    @staticmethod
    def create(
        detector_type: str = "opencv",
        async_enabled: bool = False,
        thread_pool: Optional["ThreadPoolManager"] = None,
        **kwargs,
    ) -> IFaceDetector:
        """Create a face detector instance.

        Args:
            detector_type: Type of detector to create
                Options: "opencv", "ssd", "mtcnn", "retinaface", "mediapipe", "yolov8"
            async_enabled: If True, wrap with AsyncFaceDetector for non-blocking detection
            thread_pool: Thread pool manager for async execution (required if async_enabled)
            **kwargs: Additional arguments passed to detector constructor

        Returns:
            Face detector instance implementing IFaceDetector
            If async_enabled, returns AsyncFaceDetector wrapper

        Raises:
            ValueError: If detector_type is not supported
            ValueError: If async_enabled but thread_pool is None

        Example:
            ```python
            # Synchronous detector
            detector = FaceDetectorFactory.create("mtcnn", align=True)

            # Async detector with thread pool
            pool = ThreadPoolManager(max_workers=4)
            detector = FaceDetectorFactory.create(
                "mtcnn",
                async_enabled=True,
                thread_pool=pool,
                align=True
            )
            ```
        """
        detector_type = detector_type.lower()

        logger.info(
            f"Creating face detector: {detector_type} "
            f"(async={async_enabled})"
        )

        # Validate detector type
        supported_types = [
            "opencv",
            "ssd",
            "mtcnn",
            "retinaface",
            "mediapipe",
            "yolov8",
        ]

        if detector_type not in supported_types:
            raise ValueError(
                f"Unsupported detector type: {detector_type}. "
                f"Supported types: {', '.join(supported_types)}"
            )

        # Create base detector
        base_detector = DeepFaceDetector(detector_backend=detector_type, **kwargs)

        # Wrap with async if requested
        if async_enabled:
            if thread_pool is None:
                raise ValueError(
                    "thread_pool is required when async_enabled=True"
                )
            from app.infrastructure.async_execution.async_face_detector import (
                AsyncFaceDetector,
            )
            return AsyncFaceDetector(base_detector, thread_pool)

        return base_detector

    @staticmethod
    def get_available_detectors() -> list[str]:
        """Get list of available detector types.

        Returns:
            List of supported detector type names
        """
        return ["opencv", "ssd", "mtcnn", "retinaface", "mediapipe", "yolov8"]

    @staticmethod
    def get_recommended_detector() -> str:
        """Get recommended detector for production use.

        Returns:
            Recommended detector type name
        """
        return "mtcnn"  # Good balance of speed and accuracy
