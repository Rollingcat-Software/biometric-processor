"""Domain interfaces (protocols) for biometric processor.

This module defines the contracts that infrastructure implementations must follow.
Following Dependency Inversion Principle: high-level modules depend on these abstractions.
"""

from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.file_storage import IFileStorage
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

__all__ = [
    "IFaceDetector",
    "IEmbeddingExtractor",
    "IQualityAssessor",
    "ISimilarityCalculator",
    "IEmbeddingRepository",
    "IFileStorage",
    "ILivenessDetector",
]
