"""In-memory embedding repository implementation."""

import logging
from typing import Optional, List, Tuple, Dict
from datetime import datetime
import numpy as np

from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.exceptions.repository_errors import RepositoryError

logger = logging.getLogger(__name__)


class InMemoryEmbeddingRepository:
    """In-memory embedding repository for MVP and testing.

    Implements IEmbeddingRepository using a simple dictionary for storage.
    This is suitable for development, testing, and small-scale demos.

    Following Repository Pattern for data access abstraction.

    Note:
        - Data is lost when the application restarts
        - Not suitable for production at scale
        - Will be replaced with PostgreSQL repository in Sprint 4

    Thread Safety:
        This implementation is NOT thread-safe. For production with multiple
        workers, use PostgreSQL repository or add proper locking.
    """

    def __init__(self) -> None:
        """Initialize in-memory repository."""
        # Structure: {(user_id, tenant_id): {embedding, quality_score, created_at}}
        self._embeddings: Dict[Tuple[str, Optional[str]], Dict] = {}

        logger.warning(
            "Using InMemoryEmbeddingRepository - data will be lost on restart. "
            "Replace with PostgreSQL repository for production!"
        )

    async def save(
        self,
        user_id: str,
        embedding: np.ndarray,
        quality_score: float,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Save or update a face embedding.

        Args:
            user_id: Unique identifier for the user
            embedding: Face embedding vector
            quality_score: Quality score of enrolled face (0-100)
            tenant_id: Optional tenant identifier

        Raises:
            RepositoryError: When save operation fails
        """
        try:
            key = (user_id, tenant_id)

            # Check if embedding already exists
            if key in self._embeddings:
                logger.info(f"Updating existing embedding for user {user_id}")
                self._embeddings[key].update(
                    {
                        "embedding": embedding.copy(),
                        "quality_score": quality_score,
                        "updated_at": datetime.utcnow(),
                    }
                )
            else:
                logger.info(f"Creating new embedding for user {user_id}")
                self._embeddings[key] = {
                    "embedding": embedding.copy(),
                    "quality_score": quality_score,
                    "created_at": datetime.utcnow(),
                    "updated_at": None,
                }

            logger.info(
                f"Embedding saved: user_id={user_id}, "
                f"tenant_id={tenant_id}, "
                f"dimension={len(embedding)}, "
                f"quality={quality_score:.1f}"
            )

        except Exception as e:
            logger.error(f"Failed to save embedding: {e}", exc_info=True)
            raise RepositoryError(operation="save", reason=str(e))

    async def find_by_user_id(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """Find embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            Embedding vector if found, None otherwise
        """
        try:
            key = (user_id, tenant_id)

            if key in self._embeddings:
                embedding = self._embeddings[key]["embedding"]
                logger.debug(f"Found embedding for user {user_id}")
                return embedding.copy()
            else:
                logger.debug(f"No embedding found for user {user_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to find embedding: {e}", exc_info=True)
            raise RepositoryError(operation="find", reason=str(e))

    async def find_similar(
        self,
        embedding: np.ndarray,
        threshold: float,
        limit: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """Find similar embeddings using brute-force search.

        Args:
            embedding: Query embedding vector
            threshold: Maximum distance to consider as similar
            limit: Maximum number of results to return
            tenant_id: Optional tenant identifier

        Returns:
            List of (user_id, distance) tuples, sorted by distance (ascending)

        Note:
            This uses brute-force cosine distance calculation.
            For production, use PostgreSQL with pgvector for efficient search.
        """
        try:
            matches: List[Tuple[str, float]] = []

            # Calculate distance to all embeddings
            for (user_id, stored_tenant_id), data in self._embeddings.items():
                # Filter by tenant if specified
                if tenant_id is not None and stored_tenant_id != tenant_id:
                    continue

                stored_embedding = data["embedding"]

                # Calculate cosine distance
                distance = self._cosine_distance(embedding, stored_embedding)

                # Add if below threshold
                if distance < threshold:
                    matches.append((user_id, distance))

            # Sort by distance (ascending - lower is more similar)
            matches.sort(key=lambda x: x[1])

            # Limit results
            matches = matches[:limit]

            logger.info(
                f"Found {len(matches)} similar embeddings "
                f"(threshold={threshold}, limit={limit})"
            )

            return matches

        except Exception as e:
            logger.error(f"Failed to search embeddings: {e}", exc_info=True)
            raise RepositoryError(operation="find_similar", reason=str(e))

    async def delete(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if embedding was deleted, False if not found
        """
        try:
            key = (user_id, tenant_id)

            if key in self._embeddings:
                del self._embeddings[key]
                logger.info(f"Deleted embedding for user {user_id}")
                return True
            else:
                logger.debug(f"No embedding to delete for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}", exc_info=True)
            raise RepositoryError(operation="delete", reason=str(e))

    async def exists(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Check if embedding exists for user.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if embedding exists
        """
        key = (user_id, tenant_id)
        return key in self._embeddings

    async def count(self, tenant_id: Optional[str] = None) -> int:
        """Count total number of embeddings.

        Args:
            tenant_id: Optional tenant identifier

        Returns:
            Number of stored embeddings
        """
        if tenant_id is None:
            return len(self._embeddings)
        else:
            return sum(
                1
                for (_, stored_tenant_id) in self._embeddings.keys()
                if stored_tenant_id == tenant_id
            )

    def clear(self) -> None:
        """Clear all embeddings (for testing)."""
        self._embeddings.clear()
        logger.warning("All embeddings cleared from memory")

    @staticmethod
    def _cosine_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine distance between two embeddings.

        Args:
            emb1: First embedding
            emb2: Second embedding

        Returns:
            Cosine distance (0.0 = identical, 1.0 = opposite)
        """
        # L2 normalize
        emb1_norm = emb1 / np.linalg.norm(emb1)
        emb2_norm = emb2 / np.linalg.norm(emb2)

        # Cosine similarity
        similarity = np.dot(emb1_norm, emb2_norm)

        # Convert to distance
        distance = 1.0 - similarity

        return float(np.clip(distance, 0.0, 1.0))
