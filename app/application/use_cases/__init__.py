"""Use cases for biometric processor application.

Each use case represents a single business operation following
the Single Responsibility Principle.
"""

from app.application.use_cases.batch_process import (
    BatchEnrollmentResult,
    BatchEnrollmentUseCase,
    BatchItemResult,
    BatchOperationStatus,
    BatchVerificationResult,
    BatchVerificationUseCase,
    EnrollmentItem,
    VerificationItem,
)
from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.application.use_cases.search_face import SearchFaceUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase

__all__ = [
    "EnrollFaceUseCase",
    "VerifyFaceUseCase",
    "CheckLivenessUseCase",
    "SearchFaceUseCase",
    "BatchEnrollmentUseCase",
    "BatchVerificationUseCase",
    "BatchEnrollmentResult",
    "BatchVerificationResult",
    "BatchItemResult",
    "BatchOperationStatus",
    "EnrollmentItem",
    "VerificationItem",
]
