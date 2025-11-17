"""Domain entities for biometric processor.

Entities represent core business objects with identity.
These are framework-independent and contain no infrastructure dependencies.
"""

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.verification_result import VerificationResult

__all__ = [
    "FaceDetectionResult",
    "QualityAssessment",
    "FaceEmbedding",
    "LivenessResult",
    "VerificationResult",
]
