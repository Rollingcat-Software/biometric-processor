"""Factory for creating face detectors."""

import logging

from app.domain.interfaces.face_detector import IFaceDetector
from app.infrastructure.ml.detectors.deepface_detector import DeepFaceDetector

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
    """

    @staticmethod
    def create(detector_type: str = "opencv", **kwargs) -> IFaceDetector:
        """Create a face detector instance.

        Args:
            detector_type: Type of detector to create
                Options: "opencv", "ssd", "mtcnn", "retinaface", "mediapipe", "yolov8"
            **kwargs: Additional arguments passed to detector constructor

        Returns:
            Face detector instance implementing IFaceDetector

        Raises:
            ValueError: If detector_type is not supported

        Example:
            ```python
            detector = FaceDetectorFactory.create("mtcnn", align=True)
            ```
        """
        detector_type = detector_type.lower()

        logger.info(f"Creating face detector: {detector_type}")

        # Currently only DeepFace-based detectors
        # Can be extended with other implementations (e.g., dlib, custom models)
        if detector_type in [
            "opencv",
            "ssd",
            "mtcnn",
            "retinaface",
            "mediapipe",
            "yolov8",
        ]:
            return DeepFaceDetector(detector_backend=detector_type, **kwargs)
        else:
            raise ValueError(
                f"Unsupported detector type: {detector_type}. "
                f"Supported types: opencv, ssd, mtcnn, retinaface, mediapipe, yolov8"
            )

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
