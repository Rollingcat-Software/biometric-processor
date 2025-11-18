"""Face detector interface following Interface Segregation Principle."""

from typing import Protocol

import numpy as np

from app.domain.entities.face_detection import FaceDetectionResult


class IFaceDetector(Protocol):
    """Protocol for face detection implementations.

    Implementations can use different algorithms (MTCNN, MediaPipe, RetinaFace, etc.)
    without changing client code (Open/Closed Principle).
    """

    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect faces in an image.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            FaceDetectionResult containing detection information

        Raises:
            FaceNotDetectedError: When no face is found in the image
            MultipleFacesError: When multiple faces are detected

        Note:
            This method enforces single-face detection. For multi-face detection,
            use a different interface or extend this protocol.
        """
        ...
