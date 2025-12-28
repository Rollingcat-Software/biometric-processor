"""Liveness check use case."""

import logging
from typing import Tuple

import cv2
import numpy as np

from app.domain.entities.liveness_result import LivenessResult
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.liveness_detector import ILivenessDetector

logger = logging.getLogger(__name__)


class CheckLivenessUseCase:
    """Use case for checking liveness of a face.

    This use case orchestrates the following steps:
    1. Detect face in image
    2. Crop to face region with padding
    3. Perform liveness check on cropped face

    Following Single Responsibility Principle: Only handles liveness check orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    # Padding ratio around the face for better context
    FACE_PADDING_RATIO = 0.4

    def __init__(
        self,
        detector: IFaceDetector,
        liveness_detector: ILivenessDetector,
    ) -> None:
        """Initialize liveness check use case.

        Args:
            detector: Face detector implementation
            liveness_detector: Liveness detector implementation
        """
        self._detector = detector
        self._liveness_detector = liveness_detector

        logger.info("CheckLivenessUseCase initialized")

    def _crop_face_region(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int],
        padding_ratio: float = 0.4,
    ) -> np.ndarray:
        """Crop face region from image with padding.

        Args:
            image: Full image as numpy array
            bbox: Face bounding box (x, y, width, height)
            padding_ratio: Ratio of padding to add around face

        Returns:
            Cropped face region as numpy array
        """
        h, w = image.shape[:2]
        x, y, box_w, box_h = bbox

        # Calculate padding
        pad_w = int(box_w * padding_ratio)
        pad_h = int(box_h * padding_ratio)

        # Calculate crop coordinates with padding, clamped to image bounds
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(w, x + box_w + pad_w)
        y2 = min(h, y + box_h + pad_h)

        # Crop the face region
        cropped = image[y1:y2, x1:x2]

        logger.debug(
            f"Cropped face region: original={w}x{h}, "
            f"bbox=({x},{y},{box_w},{box_h}), "
            f"cropped={cropped.shape[1]}x{cropped.shape[0]}"
        )

        return cropped

    async def execute(self, image_path: str) -> LivenessResult:
        """Execute liveness check.

        Args:
            image_path: Path to image file

        Returns:
            LivenessResult with liveness check outcome

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            LivenessCheckError: When liveness check fails
        """
        logger.info("Starting liveness check")

        # Step 1: Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Step 2: Detect face (to ensure there's a face before liveness check)
        logger.debug("Step 1/3: Detecting face...")
        detection = await self._detector.detect(image)

        logger.debug(f"Face detected with confidence: {detection.confidence:.2f}")

        # Step 3: Crop to face region for better liveness analysis
        logger.debug("Step 2/3: Cropping to face region...")
        face_image = self._crop_face_region(
            image,
            detection.bbox,
            padding_ratio=self.FACE_PADDING_RATIO,
        )

        # Ensure cropped image is large enough for analysis
        min_size = 100
        if face_image.shape[0] < min_size or face_image.shape[1] < min_size:
            logger.warning(
                f"Face crop too small ({face_image.shape}), using full image"
            )
            face_image = image

        # Step 4: Perform liveness check on cropped face
        logger.debug("Step 3/3: Checking liveness...")
        liveness_result = await self._liveness_detector.check_liveness(face_image)

        logger.info(
            f"Liveness check completed: "
            f"is_live={liveness_result.is_live}, "
            f"score={liveness_result.liveness_score:.1f}, "
            f"challenge={liveness_result.challenge}"
        )

        return liveness_result
