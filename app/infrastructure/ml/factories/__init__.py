"""Factory classes for creating ML components.

Factories implement the Factory Pattern, allowing creation of
different implementations without tight coupling.
"""

from app.infrastructure.ml.factories.detector_factory import FaceDetectorFactory
from app.infrastructure.ml.factories.extractor_factory import EmbeddingExtractorFactory
from app.infrastructure.ml.factories.liveness_factory import LivenessDetectorFactory
from app.infrastructure.ml.factories.similarity_factory import SimilarityCalculatorFactory

__all__ = [
    "FaceDetectorFactory",
    "EmbeddingExtractorFactory",
    "LivenessDetectorFactory",
    "SimilarityCalculatorFactory",
]
