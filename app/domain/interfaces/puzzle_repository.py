"""Puzzle repository interface following Repository Pattern.

This module defines the interface for puzzle persistence,
allowing different storage backends without changing business logic.
"""

from typing import Optional, Protocol

from app.domain.entities.puzzle import Puzzle


class IPuzzleRepository(Protocol):
    """Protocol for puzzle persistence implementations.

    Abstracts data access layer, allowing different storage backends
    (Redis, PostgreSQL, In-Memory, etc.) without changing business logic.

    This follows the Repository Pattern for data access abstraction.

    Note:
        - Puzzles are short-lived entities (5 minutes default TTL)
        - Redis is the recommended backend for performance
        - All methods are async for consistency with other repositories
    """

    async def save(self, puzzle: Puzzle) -> None:
        """Save puzzle with automatic TTL.

        Args:
            puzzle: Puzzle entity to save

        Raises:
            RepositoryError: When save operation fails

        Note:
            TTL is calculated from puzzle.expires_at
            If puzzle already exists, it will be updated
        """
        ...

    async def get(self, puzzle_id: str) -> Optional[Puzzle]:
        """Get puzzle by ID.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            Puzzle entity if found, None otherwise

        Note:
            Returns None for expired puzzles (cleaned up by TTL)
        """
        ...

    async def delete(self, puzzle_id: str) -> bool:
        """Delete puzzle by ID.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            True if puzzle was deleted, False if not found

        Raises:
            RepositoryError: When delete operation fails
        """
        ...

    async def exists(self, puzzle_id: str) -> bool:
        """Check if puzzle exists.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            True if puzzle exists and is not expired
        """
        ...

    async def mark_completed(
        self, puzzle_id: str, completion_time: float
    ) -> bool:
        """Mark puzzle as completed.

        Args:
            puzzle_id: Unique puzzle identifier
            completion_time: Time taken to complete in seconds

        Returns:
            True if puzzle was marked completed, False if not found

        Note:
            This is an atomic operation to prevent race conditions
        """
        ...
