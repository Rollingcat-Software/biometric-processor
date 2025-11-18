"""Domain exceptions for biometric processor.

All domain exceptions inherit from BiometricProcessorError.
This provides a clean exception hierarchy for error handling.
"""

from app.domain.exceptions.base import BiometricProcessorError
from app.domain.exceptions.face_errors import (
    EmbeddingExtractionError,
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
)
from app.domain.exceptions.liveness_errors import LivenessCheckError, LivenessCheckFailedError
from app.domain.exceptions.repository_errors import EmbeddingAlreadyExistsError, RepositoryError
from app.domain.exceptions.storage_errors import FileStorageError
from app.domain.exceptions.verification_errors import (
    EmbeddingNotFoundError,
    VerificationFailedError,
)

__all__ = [
    "BiometricProcessorError",
    "FaceNotDetectedError",
    "MultipleFacesError",
    "PoorImageQualityError",
    "EmbeddingExtractionError",
    "EmbeddingNotFoundError",
    "VerificationFailedError",
    "LivenessCheckFailedError",
    "LivenessCheckError",
    "RepositoryError",
    "EmbeddingAlreadyExistsError",
    "FileStorageError",
]
