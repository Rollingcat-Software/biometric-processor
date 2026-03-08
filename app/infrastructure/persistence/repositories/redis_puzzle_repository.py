"""Redis-backed puzzle repository implementation.

This module provides a Redis-based implementation of the puzzle repository
with automatic TTL handling for puzzle expiration.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as redis

from app.domain.entities.puzzle import Puzzle
from app.domain.interfaces.puzzle_repository import IPuzzleRepository

logger = logging.getLogger(__name__)


class PuzzleRepositoryError(Exception):
    """Base exception for puzzle repository operations."""

    pass


class RedisPuzzleRepository(IPuzzleRepository):
    """Redis-backed puzzle repository with TTL support.

    This implementation uses Redis for fast puzzle storage with
    automatic expiration based on puzzle.expires_at.

    Features:
    - Automatic TTL handling (puzzles expire automatically)
    - JSON serialization for puzzle state
    - Atomic operations for thread safety
    - Connection pooling for performance

    Attributes:
        redis_client: Async Redis client
        key_prefix: Prefix for puzzle keys in Redis
    """

    KEY_PREFIX = "liveness:puzzle:"
    MIN_TTL_SECONDS = 60  # Minimum TTL to prevent immediate expiration

    def __init__(
        self,
        redis_url: str,
        max_connections: int = 10,
        decode_responses: bool = True,
    ):
        """Initialize Redis puzzle repository.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
            max_connections: Maximum number of connections in the pool
            decode_responses: Whether to decode responses to strings
        """
        self.redis_url = redis_url
        self._pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            decode_responses=decode_responses,
        )
        self._client: Optional[redis.Redis] = None
        logger.info(f"RedisPuzzleRepository initialized with URL: {redis_url[:20]}...")

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client.

        Returns:
            Async Redis client instance
        """
        if self._client is None:
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client

    def _key(self, puzzle_id: str) -> str:
        """Generate Redis key for puzzle.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            Redis key with prefix
        """
        return f"{self.KEY_PREFIX}{puzzle_id}"

    def _calculate_ttl(self, puzzle: Puzzle) -> int:
        """Calculate TTL in seconds from puzzle expiration.

        Args:
            puzzle: Puzzle entity

        Returns:
            TTL in seconds (minimum MIN_TTL_SECONDS)
        """
        if puzzle.expires_at is None:
            return self.MIN_TTL_SECONDS

        now = datetime.utcnow()
        ttl = int((puzzle.expires_at - now).total_seconds())
        return max(ttl, self.MIN_TTL_SECONDS)

    async def save(self, puzzle: Puzzle) -> None:
        """Save puzzle with automatic TTL.

        Args:
            puzzle: Puzzle entity to save

        Raises:
            PuzzleRepositoryError: When save operation fails
        """
        try:
            client = await self._get_client()
            key = self._key(puzzle.puzzle_id)
            ttl = self._calculate_ttl(puzzle)
            data = json.dumps(puzzle.to_dict())

            await client.setex(key, ttl, data)

            logger.debug(
                f"Saved puzzle {puzzle.puzzle_id} with TTL={ttl}s, "
                f"steps={len(puzzle.steps)}, difficulty={puzzle.difficulty.value}"
            )
        except redis.RedisError as e:
            logger.error(f"Failed to save puzzle {puzzle.puzzle_id}: {e}")
            raise PuzzleRepositoryError(f"Failed to save puzzle: {e}") from e

    async def get(self, puzzle_id: str) -> Optional[Puzzle]:
        """Get puzzle by ID.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            Puzzle entity if found, None otherwise
        """
        try:
            client = await self._get_client()
            key = self._key(puzzle_id)
            data = await client.get(key)

            if data is None:
                logger.debug(f"Puzzle {puzzle_id} not found")
                return None

            puzzle = Puzzle.from_dict(json.loads(data))
            logger.debug(f"Retrieved puzzle {puzzle_id}")
            return puzzle
        except redis.RedisError as e:
            logger.error(f"Failed to get puzzle {puzzle_id}: {e}")
            raise PuzzleRepositoryError(f"Failed to get puzzle: {e}") from e
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to deserialize puzzle {puzzle_id}: {e}")
            return None

    async def delete(self, puzzle_id: str) -> bool:
        """Delete puzzle by ID.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            True if puzzle was deleted, False if not found
        """
        try:
            client = await self._get_client()
            key = self._key(puzzle_id)
            result = await client.delete(key)

            deleted = result > 0
            logger.debug(f"Delete puzzle {puzzle_id}: {'success' if deleted else 'not found'}")
            return deleted
        except redis.RedisError as e:
            logger.error(f"Failed to delete puzzle {puzzle_id}: {e}")
            raise PuzzleRepositoryError(f"Failed to delete puzzle: {e}") from e

    async def exists(self, puzzle_id: str) -> bool:
        """Check if puzzle exists.

        Args:
            puzzle_id: Unique puzzle identifier

        Returns:
            True if puzzle exists and is not expired
        """
        try:
            client = await self._get_client()
            key = self._key(puzzle_id)
            result = await client.exists(key)
            return result > 0
        except redis.RedisError as e:
            logger.error(f"Failed to check puzzle existence {puzzle_id}: {e}")
            raise PuzzleRepositoryError(f"Failed to check puzzle existence: {e}") from e

    async def mark_completed(
        self, puzzle_id: str, completion_time: float
    ) -> bool:
        """Mark puzzle as completed atomically.

        Args:
            puzzle_id: Unique puzzle identifier
            completion_time: Time taken to complete in seconds

        Returns:
            True if puzzle was marked completed, False if not found
        """
        try:
            client = await self._get_client()
            key = self._key(puzzle_id)

            # Use WATCH for optimistic locking
            async with client.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        # Watch the key for changes
                        await pipe.watch(key)

                        # Get current value
                        data = await pipe.get(key)
                        if data is None:
                            await pipe.unwatch()
                            return False

                        # Update puzzle
                        puzzle = Puzzle.from_dict(json.loads(data))
                        puzzle.mark_completed(completion_time)

                        # Start transaction
                        pipe.multi()

                        # Calculate new TTL (keep for audit, but shorter)
                        ttl = min(self._calculate_ttl(puzzle), 300)  # Max 5 min after completion

                        pipe.setex(key, ttl, json.dumps(puzzle.to_dict()))

                        # Execute transaction
                        await pipe.execute()
                        logger.info(
                            f"Marked puzzle {puzzle_id} as completed "
                            f"in {completion_time:.2f}s"
                        )
                        return True

                    except redis.WatchError:
                        # Key was modified, retry
                        logger.warning(f"Concurrent modification of puzzle {puzzle_id}, retrying")
                        continue

        except redis.RedisError as e:
            logger.error(f"Failed to mark puzzle completed {puzzle_id}: {e}")
            raise PuzzleRepositoryError(f"Failed to mark puzzle completed: {e}") from e

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._client:
            await self._client.close()
            self._client = None
        logger.info("RedisPuzzleRepository closed")


class InMemoryPuzzleRepository(IPuzzleRepository):
    """In-memory puzzle repository for testing.

    Warning:
        This implementation is NOT suitable for production use.
        Puzzles are not persisted and will be lost on restart.
        No TTL enforcement - puzzles must be manually cleaned up.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._storage: dict[str, Puzzle] = {}
        logger.warning(
            "Using InMemoryPuzzleRepository - NOT for production use!"
        )

    async def save(self, puzzle: Puzzle) -> None:
        """Save puzzle to memory."""
        self._storage[puzzle.puzzle_id] = puzzle
        logger.debug(f"Saved puzzle {puzzle.puzzle_id} (in-memory)")

    async def get(self, puzzle_id: str) -> Optional[Puzzle]:
        """Get puzzle from memory."""
        puzzle = self._storage.get(puzzle_id)
        if puzzle and puzzle.is_expired():
            del self._storage[puzzle_id]
            return None
        return puzzle

    async def delete(self, puzzle_id: str) -> bool:
        """Delete puzzle from memory."""
        if puzzle_id in self._storage:
            del self._storage[puzzle_id]
            return True
        return False

    async def exists(self, puzzle_id: str) -> bool:
        """Check if puzzle exists in memory."""
        puzzle = self._storage.get(puzzle_id)
        if puzzle and puzzle.is_expired():
            del self._storage[puzzle_id]
            return False
        return puzzle is not None

    async def mark_completed(
        self, puzzle_id: str, completion_time: float
    ) -> bool:
        """Mark puzzle as completed in memory."""
        puzzle = self._storage.get(puzzle_id)
        if puzzle is None:
            return False
        puzzle.mark_completed(completion_time)
        return True

    async def close(self) -> None:
        """Clear in-memory storage."""
        self._storage.clear()
