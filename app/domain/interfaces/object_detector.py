"""Object detector interface."""

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

import numpy as np

from app.domain.entities.proctor_analysis import ObjectDetectionResult


class IObjectDetector(ABC):
    """Interface for object detection."""

    @abstractmethod
    async def detect(
        self,
        image: np.ndarray,
        session_id: UUID,
        prohibited_objects: List[str] = None,
    ) -> ObjectDetectionResult:
        """Detect objects in image.

        Args:
            image: BGR image array
            session_id: Session being analyzed
            prohibited_objects: List of prohibited object labels

        Returns:
            ObjectDetectionResult with detected objects
        """
        pass

    @abstractmethod
    def get_supported_objects(self) -> List[str]:
        """Get list of supported object labels."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if object detector is available."""
        pass
