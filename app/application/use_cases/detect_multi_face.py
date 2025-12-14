"""Detect multiple faces use case."""

import logging
from typing import List

import numpy as np

from app.domain.entities.multi_face_result import (
    BasicLandmarks,
    BoundingBox,
    DetectedFace,
    MultiFaceResult,
)
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor

logger = logging.getLogger(__name__)


class DetectMultiFaceUseCase:
    """Use case for detecting multiple faces in an image.

    Returns information about all detected faces including
    bounding boxes, quality scores, and basic landmarks.
    """

    MAX_FACES = 10  # Maximum number of faces to return

    def __init__(
        self,
        detector: IFaceDetector,
        quality_assessor: IQualityAssessor,
    ) -> None:
        """Initialize multi-face detection use case.

        Args:
            detector: Face detector implementation
            quality_assessor: Quality assessor implementation
        """
        self._detector = detector
        self._quality_assessor = quality_assessor
        logger.info("DetectMultiFaceUseCase initialized")

    async def execute(
        self, image: np.ndarray, max_faces: int = None
    ) -> MultiFaceResult:
        """Execute multi-face detection.

        Args:
            image: Input image as numpy array (RGB format)
            max_faces: Maximum faces to return (default: MAX_FACES)

        Returns:
            MultiFaceResult with all detected faces
        """
        logger.info("Starting multi-face detection")

        max_faces = max_faces or self.MAX_FACES
        height, width = image.shape[:2]

        # Detect all faces
        faces = await self._detect_all_faces(image)

        # Limit number of faces
        faces = faces[:max_faces]

        # Assess quality for each face
        detected_faces = []
        for idx, face in enumerate(faces):
            quality_score = await self._assess_face_quality(image, face)
            detected_face = self._create_detected_face(idx, face, quality_score)
            detected_faces.append(detected_face)

        # Sort by confidence (highest first)
        detected_faces.sort(key=lambda f: f.confidence, reverse=True)

        result = MultiFaceResult(
            face_count=len(detected_faces),
            faces=detected_faces,
            image_width=width,
            image_height=height,
        )

        logger.info(f"Multi-face detection complete: {len(detected_faces)} faces found")
        return result

    async def _detect_all_faces(self, image: np.ndarray) -> List[dict]:
        """Detect all faces in image.

        Returns list of face dictionaries with bounding box, confidence, landmarks.
        """
        # Use detector with enforce_detection=False to get all faces
        faces = []

        # Most detectors return single result - we need to handle multi-face
        # This is a simplified implementation
        try:
            result = await self._detector.detect(image)

            if result.found:
                face_data = {
                    "bbox": result.bounding_box,
                    "confidence": result.confidence,
                    "landmarks": result.landmarks,
                }
                faces.append(face_data)

                # Try to find additional faces by processing regions
                # This is a basic approach - production would use batch detection
                x, y, w, h = result.bounding_box

                # Mask out detected face and try to find more
                remaining_faces = self._find_additional_faces(image, [(x, y, w, h)])
                faces.extend(remaining_faces)
        except Exception as e:
            logger.warning(f"Face detection failed: {e}")

        return faces

    def _find_additional_faces(
        self, image: np.ndarray, excluded_regions: List[tuple]
    ) -> List[dict]:
        """Find additional faces excluding already detected regions.

        This is a placeholder for more sophisticated multi-face detection.
        In production, use a detector that natively supports multiple faces.
        """
        # Placeholder - would implement region-based detection
        return []

    async def _assess_face_quality(self, image: np.ndarray, face: dict) -> float:
        """Assess quality of detected face."""
        try:
            x, y, w, h = face["bbox"]
            face_region = image[y : y + h, x : x + w]
            result = await self._quality_assessor.assess(face_region)
            return result.score
        except Exception as e:
            logger.warning(f"Quality assessment failed: {e}")
            return 0.0

    def _create_detected_face(
        self, idx: int, face: dict, quality_score: float
    ) -> DetectedFace:
        """Create DetectedFace from detection data."""
        x, y, w, h = face["bbox"]
        bbox = BoundingBox(x=x, y=y, width=w, height=h)

        # Extract landmarks if available
        landmarks = None
        if face.get("landmarks"):
            lm = face["landmarks"]
            landmarks = BasicLandmarks(
                left_eye=lm.get("left_eye", (x + w // 4, y + h // 3)),
                right_eye=lm.get("right_eye", (x + 3 * w // 4, y + h // 3)),
                nose=lm.get("nose", (x + w // 2, y + h // 2)),
                mouth_left=lm.get("mouth_left", (x + w // 3, y + 2 * h // 3)),
                mouth_right=lm.get("mouth_right", (x + 2 * w // 3, y + 2 * h // 3)),
            )

        return DetectedFace(
            face_id=idx,
            bounding_box=bbox,
            confidence=face.get("confidence", 0.95),
            quality_score=quality_score,
            landmarks=landmarks,
        )
