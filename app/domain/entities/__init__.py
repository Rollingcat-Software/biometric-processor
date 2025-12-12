"""Domain entities for biometric processor.

Entities represent core business objects with identity.
These are framework-independent and contain no infrastructure dependencies.
"""

from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.face_embedding import FaceEmbedding
from app.domain.entities.liveness_result import LivenessResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.entities.verification_result import VerificationResult

# Proctoring entities
from app.domain.entities.proctor_session import (
    ProctorSession,
    SessionConfig,
    SessionStatus,
    TerminationReason,
)
from app.domain.entities.proctor_incident import (
    IncidentEvidence,
    IncidentSeverity,
    IncidentType,
    ProctorIncident,
    ReviewAction,
)
from app.domain.entities.proctor_analysis import (
    AudioAnalysisResult,
    DeepfakeAnalysisResult,
    DetectedObject,
    FrameAnalysisResult,
    GazeAnalysisResult,
    GazeDirection,
    HeadPose,
    ObjectDetectionResult,
    VerificationEvent,
)

__all__ = [
    "FaceDetectionResult",
    "QualityAssessment",
    "FaceEmbedding",
    "LivenessResult",
    "VerificationResult",
    # Proctoring
    "ProctorSession",
    "SessionConfig",
    "SessionStatus",
    "TerminationReason",
    "ProctorIncident",
    "IncidentEvidence",
    "IncidentSeverity",
    "IncidentType",
    "ReviewAction",
    "FrameAnalysisResult",
    "GazeAnalysisResult",
    "GazeDirection",
    "HeadPose",
    "ObjectDetectionResult",
    "DetectedObject",
    "AudioAnalysisResult",
    "DeepfakeAnalysisResult",
    "VerificationEvent",
]
