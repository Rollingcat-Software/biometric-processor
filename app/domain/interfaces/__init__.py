"""Domain interfaces (protocols) for biometric processor.

This module defines the contracts that infrastructure implementations must follow.
Following Dependency Inversion Principle: high-level modules depend on these abstractions.
"""

from app.domain.interfaces.card_type_detector import ICardTypeDetector
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.file_storage import IFileStorage
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

# Proctoring interfaces
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository
from app.domain.interfaces.gaze_tracker import IGazeTracker
from app.domain.interfaces.object_detector import IObjectDetector
from app.domain.interfaces.audio_analyzer import IAudioAnalyzer
from app.domain.interfaces.deepfake_detector import IDeepfakeDetector

__all__ = [
    "ICardTypeDetector",
    "IFaceDetector",
    "IEmbeddingExtractor",
    "IQualityAssessor",
    "ISimilarityCalculator",
    "IEmbeddingRepository",
    "IFileStorage",
    "ILivenessDetector",
    # Proctoring
    "IProctorSessionRepository",
    "IProctorIncidentRepository",
    "IGazeTracker",
    "IObjectDetector",
    "IAudioAnalyzer",
    "IDeepfakeDetector",
]
