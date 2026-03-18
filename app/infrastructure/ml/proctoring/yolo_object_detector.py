"""YOLO-based object detector for proctoring.

Uses Ultralytics YOLO to detect prohibited objects during proctored exams:
- Cell phones
- Additional people
- Books/notes
- Laptops/tablets
- Headphones/earbuds
"""

import logging
from datetime import datetime
from functools import lru_cache
from typing import List, Optional, Set

import numpy as np

from app.domain.entities.proctor_analysis import (
    DetectedObject,
    ObjectDetectionResult,
)
from app.domain.interfaces.object_detector import IObjectDetector

logger = logging.getLogger(__name__)

# COCO class names that are relevant for proctoring
# Full COCO has 80 classes, we care about specific ones
PROHIBITED_OBJECTS: Set[str] = {
    "cell phone",
    "book",
    "laptop",
    "remote",  # Could be phone
    "keyboard",  # External keyboard
    "mouse",  # External mouse
}

# Objects that indicate additional people
PERSON_OBJECTS: Set[str] = {
    "person",
}

# Objects that might indicate cheating aids
SUSPICIOUS_OBJECTS: Set[str] = {
    "tv",  # Could be second screen
    "monitor",
    "tablet",
    "apple",  # Sometimes misclassifies AirPods
    "headphones",
}

# All objects we want to track (subset of COCO)
TRACKED_OBJECTS: Set[str] = PROHIBITED_OBJECTS | PERSON_OBJECTS | SUSPICIOUS_OBJECTS

# Default YOLO model (YOLOv8n for speed, v8s/v8m for accuracy)
DEFAULT_MODEL = "yolov8n.pt"


@lru_cache(maxsize=1)
def _get_yolo_model(model_name: str = DEFAULT_MODEL):
    """Load YOLO model with caching."""
    from ultralytics import YOLO

    logger.info(f"Loading YOLO model: {model_name}")
    model = YOLO(model_name)
    return model


class YOLOObjectDetector(IObjectDetector):
    """Object detector for proctoring using YOLO.

    Detects and classifies objects relevant to exam proctoring,
    identifying prohibited items like phones, extra people, etc.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        confidence_threshold: float = 0.5,
        person_threshold: float = 0.6,
        max_persons_allowed: int = 1,
        custom_prohibited: Optional[Set[str]] = None,
    ) -> None:
        """Initialize YOLO object detector.

        Args:
            model_name: YOLO model to use (yolov8n, yolov8s, yolov8m)
            confidence_threshold: Minimum confidence for detection
            person_threshold: Higher threshold for person detection
            max_persons_allowed: Maximum number of persons allowed
            custom_prohibited: Additional objects to mark as prohibited
        """
        self._model_name = model_name
        self._confidence_threshold = confidence_threshold
        self._person_threshold = person_threshold
        self._max_persons_allowed = max_persons_allowed
        self._model = None

        # Build prohibited set
        self._prohibited = PROHIBITED_OBJECTS.copy()
        if custom_prohibited:
            self._prohibited.update(custom_prohibited)

        logger.info(
            f"YOLOObjectDetector initialized: model={model_name}, "
            f"threshold={confidence_threshold}, max_persons={max_persons_allowed}"
        )

    def _get_model(self):
        """Lazy load the YOLO model."""
        if self._model is None:
            self._model = _get_yolo_model(self._model_name)
        return self._model

    async def detect(
        self,
        image: np.ndarray,
        session_id,
    ) -> ObjectDetectionResult:
        """Detect objects in frame for proctoring.

        Args:
            image: BGR image array
            session_id: Session being analyzed

        Returns:
            ObjectDetectionResult with detected objects
        """
        timestamp = datetime.utcnow()

        model = self._get_model()

        # Run inference
        results = model(
            image,
            conf=self._confidence_threshold,
            verbose=False,
            classes=None,  # All classes, we filter below
        )

        result = results[0]
        detected_objects: List[DetectedObject] = []
        person_count = 0
        has_prohibited = False

        # Process detections
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = model.names[class_id].lower()

            # Skip if not in tracked objects
            if class_name not in TRACKED_OBJECTS:
                continue

            # Apply higher threshold for person detection
            if class_name == "person":
                if confidence < self._person_threshold:
                    continue
                person_count += 1

            # Get bounding box
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            bbox = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))

            # Determine if prohibited
            is_prohibited = self._is_prohibited(class_name, person_count)
            if is_prohibited:
                has_prohibited = True

            detected_objects.append(
                DetectedObject(
                    label=class_name,
                    confidence=round(confidence, 3),
                    bounding_box=bbox,
                    is_prohibited=is_prohibited,
                )
            )

        # Calculate frame quality based on image properties
        frame_quality = self._assess_frame_quality(image)

        logger.debug(
            f"Object detection: {len(detected_objects)} objects, "
            f"prohibited={has_prohibited}, persons={person_count}"
        )

        return ObjectDetectionResult(
            session_id=session_id,
            timestamp=timestamp,
            objects=detected_objects,
            has_prohibited_objects=has_prohibited,
            frame_quality=frame_quality,
        )

    def _is_prohibited(self, class_name: str, person_count: int) -> bool:
        """Determine if detected object is prohibited.

        Args:
            class_name: Object class name
            person_count: Current person count

        Returns:
            True if object is prohibited
        """
        # Direct prohibited objects
        if class_name in self._prohibited:
            return True

        # Multiple persons
        if class_name == "person" and person_count > self._max_persons_allowed:
            return True

        # Suspicious objects are flagged but not always prohibited
        if class_name in SUSPICIOUS_OBJECTS:
            return True

        return False

    def _assess_frame_quality(self, image: np.ndarray) -> float:
        """Assess frame quality for detection reliability.

        Args:
            image: Input image

        Returns:
            Quality score 0-1
        """
        import cv2

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Check blur (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(1.0, laplacian_var / 500.0)

        # Check brightness
        brightness = np.mean(gray) / 255.0
        brightness_score = 1.0 - abs(brightness - 0.5) * 2  # Optimal around 0.5

        # Combined quality
        quality = (blur_score * 0.6 + brightness_score * 0.4)
        return round(float(np.clip(quality, 0.0, 1.0)), 2)

    def get_supported_objects(self) -> List[str]:
        """Get list of objects this detector can identify.

        Returns:
            List of supported object labels
        """
        return list(TRACKED_OBJECTS)

    def get_prohibited_objects(self) -> List[str]:
        """Get list of prohibited objects.

        Returns:
            List of prohibited object labels
        """
        return list(self._prohibited)

    def set_max_persons(self, max_persons: int) -> None:
        """Set maximum allowed persons.

        Args:
            max_persons: New maximum
        """
        self._max_persons_allowed = max_persons
        logger.info(f"Max persons updated to {max_persons}")

    def add_prohibited_object(self, object_name: str) -> None:
        """Add object to prohibited list.

        Args:
            object_name: Object class name to prohibit
        """
        self._prohibited.add(object_name.lower())
        logger.info(f"Added '{object_name}' to prohibited objects")

    def is_available(self) -> bool:
        """Check if object detector is available."""
        try:
            from ultralytics import YOLO
            return True
        except ImportError:
            return False
