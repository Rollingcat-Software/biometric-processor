"""Domain exceptions for biometric processor.

All domain exceptions inherit from BiometricProcessorError.
This provides a clean exception hierarchy for error handling.
"""

from app.domain.exceptions.base import BiometricProcessorError
from app.domain.exceptions.face_errors import (
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
    EmbeddingExtractionError,
)
from app.domain.exceptions.verification_errors import (
    EmbeddingNotFoundError,
    VerificationFailedError,
)
from app.domain.exceptions.liveness_errors import (
    LivenessCheckFailedError,
    LivenessCheckError,
)
from app.domain.exceptions.repository_errors import (
    RepositoryError,
    EmbeddingAlreadyExistsError,
)
from app.domain.exceptions.storage_errors import FileStorageError

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
