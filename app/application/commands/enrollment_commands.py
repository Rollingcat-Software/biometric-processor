"""Enrollment commands for CQRS implementation.

This module contains commands related to face enrollment operations.
Commands encapsulate the intent to change system state.
"""

from dataclasses import dataclass
from typing import List, Optional

from app.application.commands.base import Command


@dataclass(frozen=True)
class EnrollFaceCommand(Command):
    """Command to enroll a single face image.

    This command represents the intent to register a user's face
    in the biometric system using a single image.

    Attributes:
        user_id: Unique identifier for the user
        image_path: Path to the face image file
        tenant_id: Optional tenant identifier for multi-tenancy
        idempotency_key: Optional key to prevent duplicate enrollments
    """

    user_id: str
    image_path: str
    tenant_id: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class EnrollMultiImageCommand(Command):
    """Command to enroll a face using multiple images.

    This command represents the intent to register a user's face
    using multiple images for improved accuracy through template fusion.

    Attributes:
        user_id: Unique identifier for the user
        image_paths: List of paths to face image files (2-5 images)
        tenant_id: Optional tenant identifier for multi-tenancy
        fusion_strategy: Strategy for combining embeddings (default: quality_weighted)
        idempotency_key: Optional key to prevent duplicate enrollments
    """

    user_id: str
    image_paths: List[str]
    tenant_id: Optional[str] = None
    fusion_strategy: str = "quality_weighted"
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class DeleteEnrollmentCommand(Command):
    """Command to delete a user's enrollment.

    This command represents the intent to remove a user's biometric data
    from the system (e.g., for GDPR compliance, account deletion).

    Attributes:
        user_id: Unique identifier for the user
        tenant_id: Optional tenant identifier for multi-tenancy
        reason: Optional reason for deletion (for audit logging)
    """

    user_id: str
    tenant_id: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class UpdateEnrollmentCommand(Command):
    """Command to update an existing enrollment.

    This command represents the intent to replace a user's existing
    biometric template with a new one.

    Attributes:
        user_id: Unique identifier for the user
        image_path: Path to the new face image file
        tenant_id: Optional tenant identifier for multi-tenancy
        force_update: If True, skip quality comparison with existing enrollment
    """

    user_id: str
    image_path: str
    tenant_id: Optional[str] = None
    force_update: bool = False


@dataclass(frozen=True)
class BatchEnrollCommand(Command):
    """Command to enroll multiple users in batch.

    This command represents the intent to register multiple users
    at once, typically for bulk onboarding scenarios.

    Attributes:
        enrollments: List of (user_id, image_path) tuples
        tenant_id: Optional tenant identifier for multi-tenancy
        max_concurrent: Maximum number of concurrent enrollments
        stop_on_error: If True, stop batch on first error
    """

    enrollments: List[tuple[str, str]]
    tenant_id: Optional[str] = None
    max_concurrent: int = 5
    stop_on_error: bool = False
