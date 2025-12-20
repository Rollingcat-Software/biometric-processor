"""Factory for creating liveness detectors."""

import logging
from typing import Literal

from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.infrastructure.ml.liveness.active_liveness_detector import ActiveLivenessDetector
from app.infrastructure.ml.liveness.combined_liveness_detector import CombinedLivenessDetector
from app.infrastructure.ml.liveness.stub_liveness_detector import StubLivenessDetector
from app.infrastructure.ml.liveness.texture_liveness_detector import TextureLivenessDetector

logger = logging.getLogger(__name__)

LivenessMode = Literal["passive", "active", "combined", "stub"]


class LivenessDetectorFactory:
    """Factory for creating liveness detector instances.

    Implements Factory Pattern for creating different liveness detector implementations.
    This allows adding new detectors without modifying client code (Open/Closed Principle).

    Supported Modes:
    - passive: Texture-based analysis (printed photos, screens)
    - active: Smile/blink detection via MediaPipe
    - combined: Both methods for highest accuracy
    - stub: Always passes (for testing)
    """

    @staticmethod
    def create(
        mode: LivenessMode = "combined",
        liveness_threshold: float = 70.0,
        **kwargs,
    ) -> ILivenessDetector:
        """Create a liveness detector instance.

        Args:
            mode: Type of liveness detection
                Options: "passive", "active", "combined", "stub"
            liveness_threshold: Score threshold for liveness (0-100)
            **kwargs: Additional arguments passed to detector constructor

        Returns:
            Liveness detector instance implementing ILivenessDetector

        Raises:
            ValueError: If mode is not supported

        Example:
            ```python
            detector = LivenessDetectorFactory.create("combined", liveness_threshold=70.0)
            ```
        """
        mode = mode.lower()

        logger.info(f"Creating liveness detector: {mode}")

        if mode == "passive":
            return TextureLivenessDetector(
                texture_threshold=kwargs.get("texture_threshold", 100.0),
                color_threshold=kwargs.get("color_threshold", 0.3),
                frequency_threshold=kwargs.get("frequency_threshold", 0.5),
                liveness_threshold=kwargs.get("passive_threshold", 60.0),
            )
        elif mode == "active":
            return ActiveLivenessDetector(
                ear_threshold=kwargs.get("ear_threshold", 0.25),
                mar_threshold=kwargs.get("mar_threshold", 0.6),
                liveness_threshold=liveness_threshold,
            )
        elif mode == "combined":
            return CombinedLivenessDetector(
                texture_weight=kwargs.get("texture_weight", 0.4),
                active_weight=kwargs.get("active_weight", 0.6),
                liveness_threshold=liveness_threshold,
            )
        elif mode == "stub":
            return StubLivenessDetector()
        else:
            raise ValueError(
                f"Unsupported liveness mode: {mode}. "
                f"Supported modes: passive, active, combined, stub"
            )

    @staticmethod
    def get_available_modes() -> list[str]:
        """Get list of available liveness modes.

        Returns:
            List of supported mode names
        """
        return ["passive", "active", "combined", "stub"]

    @staticmethod
    def get_recommended_mode() -> str:
        """Get recommended mode for production use.

        Returns:
            Recommended mode name
        """
        return "combined"  # Highest accuracy with both methods
