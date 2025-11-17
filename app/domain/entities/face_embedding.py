"""Face embedding entity."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import numpy as np


@dataclass
class FaceEmbedding:
    """Face embedding entity with identity.

    This is a domain entity representing a stored face embedding.
    Following Single Responsibility Principle - contains embedding data and metadata.

    Attributes:
        user_id: Unique identifier for the user
        vector: Face embedding as numpy array
        quality_score: Quality score of enrolled face (0-100)
        created_at: Timestamp when embedding was created
        updated_at: Timestamp when embedding was last updated
        tenant_id: Optional tenant identifier for multi-tenancy

    Note:
        Unlike value objects, entities have identity (user_id).
        Two embeddings with same user_id are considered the same entity.
    """

    user_id: str
    vector: np.ndarray
    quality_score: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    tenant_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate face embedding data."""
        if not self.user_id:
            raise ValueError("user_id cannot be empty")

        if self.vector is None or len(self.vector.shape) != 1:
            raise ValueError("vector must be 1-dimensional numpy array")

        if not 0 <= self.quality_score <= 100:
            raise ValueError(f"quality_score must be 0-100, got {self.quality_score}")

    def __eq__(self, other: object) -> bool:
        """Check equality based on user_id (entity identity).

        Args:
            other: Object to compare

        Returns:
            True if same user_id and tenant_id
        """
        if not isinstance(other, FaceEmbedding):
            return False
        return self.user_id == other.user_id and self.tenant_id == other.tenant_id

    def __hash__(self) -> int:
        """Hash based on user_id (entity identity)."""
        return hash((self.user_id, self.tenant_id))

    def get_embedding_dimension(self) -> int:
        """Get dimension of embedding vector.

        Returns:
            Embedding dimension (e.g., 128, 512)
        """
        return len(self.vector)

    def is_fresh(self, max_age_days: int = 365) -> bool:
        """Check if embedding is fresh (not too old).

        Args:
            max_age_days: Maximum age in days

        Returns:
            True if embedding is within max age
        """
        age = datetime.utcnow() - self.created_at
        return age.days <= max_age_days

    def to_list(self) -> List[float]:
        """Convert embedding vector to list for serialization.

        Returns:
            Embedding as list of floats
        """
        return self.vector.tolist()

    @classmethod
    def create_new(
        cls,
        user_id: str,
        vector: np.ndarray,
        quality_score: float,
        tenant_id: Optional[str] = None,
    ) -> "FaceEmbedding":
        """Factory method to create new face embedding.

        Args:
            user_id: User identifier
            vector: Embedding vector
            quality_score: Quality score (0-100)
            tenant_id: Optional tenant identifier

        Returns:
            New FaceEmbedding instance
        """
        return cls(
            user_id=user_id,
            vector=vector,
            quality_score=quality_score,
            created_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )

    def update(self, vector: np.ndarray, quality_score: float) -> None:
        """Update embedding with new vector and quality score.

        Args:
            vector: New embedding vector
            quality_score: New quality score

        Note:
            Updates the vector, quality score, and sets updated_at timestamp.
        """
        if len(vector) != len(self.vector):
            raise ValueError(
                f"Vector dimension mismatch: expected {len(self.vector)}, got {len(vector)}"
            )

        self.vector = vector
        self.quality_score = quality_score
        self.updated_at = datetime.utcnow()
