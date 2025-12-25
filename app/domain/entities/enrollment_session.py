"""Enrollment session entity for multi-image enrollment."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

import numpy as np


class SessionStatus(Enum):
    """Status of enrollment session."""

    PENDING = "pending"  # Waiting for images
    IN_PROGRESS = "in_progress"  # Processing images
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with errors


@dataclass
class ImageSubmission:
    """Individual image submission in enrollment session."""

    image_id: str
    quality_score: float
    embedding: np.ndarray
    submitted_at: datetime

    def __post_init__(self) -> None:
        """Validate image submission."""
        if not 0 <= self.quality_score <= 100:
            raise ValueError(f"quality_score must be 0-100, got {self.quality_score}")

        if self.embedding is None or len(self.embedding.shape) != 1:
            raise ValueError("embedding must be 1-dimensional numpy array")


@dataclass
class EnrollmentSession:
    """Enrollment session entity for multi-image enrollment.

    Tracks the state of a multi-image enrollment session where a user
    submits 2-5 face images to create a robust fused template.

    Attributes:
        session_id: Unique identifier for the session
        user_id: User being enrolled
        tenant_id: Optional tenant identifier
        status: Current status of session
        min_images: Minimum number of images required (default: 2)
        max_images: Maximum number of images allowed (default: 5)
        submissions: List of image submissions
        created_at: When session was created
        updated_at: When session was last updated
        completed_at: When session was completed (if applicable)
    """

    session_id: str
    user_id: str
    status: SessionStatus
    min_images: int = 2
    max_images: int = 5
    tenant_id: Optional[str] = None
    submissions: List[ImageSubmission] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate enrollment session."""
        if not self.session_id:
            raise ValueError("session_id cannot be empty")
        if not self.user_id:
            raise ValueError("user_id cannot be empty")
        if not 2 <= self.min_images <= self.max_images <= 5:
            raise ValueError("min_images and max_images must be between 2 and 5")

    def add_submission(
        self, image_id: str, quality_score: float, embedding: np.ndarray
    ) -> None:
        """Add an image submission to the session.

        Args:
            image_id: Unique identifier for the image
            quality_score: Quality score (0-100)
            embedding: Face embedding vector

        Raises:
            ValueError: If session is full or already completed
        """
        if self.status == SessionStatus.COMPLETED:
            raise ValueError("Cannot add submission to completed session")

        if self.is_full():
            raise ValueError(
                f"Session already has maximum {self.max_images} submissions"
            )

        submission = ImageSubmission(
            image_id=image_id,
            quality_score=quality_score,
            embedding=embedding,
            submitted_at=datetime.utcnow(),
        )

        self.submissions.append(submission)
        self.status = SessionStatus.IN_PROGRESS
        self.updated_at = datetime.utcnow()

    def get_submission_count(self) -> int:
        """Get number of submissions.

        Returns:
            Number of images submitted
        """
        return len(self.submissions)

    def is_ready_for_fusion(self) -> bool:
        """Check if session has enough images for template fusion.

        Returns:
            True if submission count >= min_images
        """
        return self.get_submission_count() >= self.min_images

    def is_full(self) -> bool:
        """Check if session has reached maximum images.

        Returns:
            True if submission count >= max_images
        """
        return self.get_submission_count() >= self.max_images

    def get_embeddings(self) -> List[np.ndarray]:
        """Get all embedding vectors from submissions.

        Returns:
            List of embedding vectors
        """
        return [sub.embedding for sub in self.submissions]

    def get_quality_scores(self) -> List[float]:
        """Get all quality scores from submissions.

        Returns:
            List of quality scores
        """
        return [sub.quality_score for sub in self.submissions]

    def get_average_quality(self) -> float:
        """Calculate average quality score across submissions.

        Returns:
            Average quality score (0-100)
        """
        if not self.submissions:
            return 0.0
        return sum(self.get_quality_scores()) / len(self.submissions)

    def mark_completed(self) -> None:
        """Mark session as completed."""
        self.status = SessionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self) -> None:
        """Mark session as failed."""
        self.status = SessionStatus.FAILED
        self.updated_at = datetime.utcnow()

    def clear_submissions(self) -> None:
        """Clear all submissions and release memory.

        This method should be called when a session fails to prevent
        memory leaks from partially processed embeddings (large numpy arrays).
        Especially important in error scenarios where the session object
        might be retained in memory temporarily.
        """
        self.submissions.clear()
        self.updated_at = datetime.utcnow()

    @classmethod
    def create_new(
        cls,
        session_id: str,
        user_id: str,
        tenant_id: Optional[str] = None,
        min_images: int = 2,
        max_images: int = 5,
    ) -> "EnrollmentSession":
        """Factory method to create new enrollment session.

        Args:
            session_id: Unique session identifier
            user_id: User identifier
            tenant_id: Optional tenant identifier
            min_images: Minimum number of images required
            max_images: Maximum number of images allowed

        Returns:
            New EnrollmentSession instance
        """
        return cls(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            status=SessionStatus.PENDING,
            min_images=min_images,
            max_images=max_images,
            submissions=[],
            created_at=datetime.utcnow(),
        )
