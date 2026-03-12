"""UniFace MiniFASNet-based liveness detector.

This detector wraps texture-based analysis as a placeholder for the
MiniFASNet model integration. When the uniface package is available,
it should be replaced with actual MiniFASNet inference.
"""

import logging

import numpy as np

from app.domain.entities.liveness_result import LivenessResult
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.infrastructure.ml.liveness.texture_liveness_detector import TextureLivenessDetector

logger = logging.getLogger(__name__)


class UniFaceLivenessDetector(ILivenessDetector):
    """Liveness detector using UniFace MiniFASNet model.

    Falls back to texture-based analysis until the uniface
    native module is installed.
    """

    def __init__(self, liveness_threshold: float = 60.0) -> None:
        self._liveness_threshold = liveness_threshold
        self._fallback = TextureLivenessDetector(
            liveness_threshold=liveness_threshold,
        )
        logger.info(
            "UniFaceLivenessDetector initialized "
            "(using texture fallback until uniface native module is available)"
        )

    async def check_liveness(self, image: np.ndarray) -> LivenessResult:
        """Check liveness using MiniFASNet model (falls back to texture analysis).

        Args:
            image: Face image as numpy array (BGR format)

        Returns:
            LivenessResult with liveness determination
        """
        return await self._fallback.check_liveness(image)

    def get_challenge_type(self) -> str:
        return "uniface_minifasnet"

    def get_liveness_threshold(self) -> float:
        return self._liveness_threshold
