"""Embedding repository interface following Repository Pattern."""

from datetime import datetime
from typing import List, Optional, Protocol, Tuple

import numpy as np


class IEmbeddingRepository(Protocol):
    """Protocol for embedding persistence implementations.

    Abstracts data access layer, allowing different storage backends
    (PostgreSQL, In-Memory, MongoDB, etc.) without changing business logic.

    This follows the Repository Pattern for data access abstraction.
    """

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
            quality_score: Quality score of the enrolled face (0-100)
            tenant_id: Optional tenant identifier for multi-tenancy

        Raises:
            RepositoryError: When save operation fails

        Note:
            If embedding exists for user_id, it will be updated.
        """
        ...

    async def find_by_user_id(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """Find embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            Embedding vector if found, None otherwise

        Note:
            For multi-tenant systems, both user_id and tenant_id must match.
        """
        ...

    async def find_similar(
        self,
        embedding: np.ndarray,
        threshold: float,
        limit: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """Find similar embeddings using vector similarity search.

        Args:
            embedding: Query embedding vector
            threshold: Maximum distance to consider as similar
            limit: Maximum number of results to return
            tenant_id: Optional tenant identifier

        Returns:
            List of (user_id, distance) tuples, sorted by distance (ascending)

        Raises:
            RepositoryError: When search operation fails

        Note:
            This is used for 1:N identification.
            Requires efficient vector similarity search (e.g., pgvector).
        """
        ...

    async def delete(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if embedding was deleted, False if not found

        Raises:
            RepositoryError: When delete operation fails
        """
        ...

    async def exists(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Check if embedding exists for user.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if embedding exists, False otherwise
        """
        ...

    async def count(self, tenant_id: Optional[str] = None) -> int:
        """Count total number of embeddings.

        Args:
            tenant_id: Optional tenant identifier

        Returns:
            Number of stored embeddings
        """
        ...
