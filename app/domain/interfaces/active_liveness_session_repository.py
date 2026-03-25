"""Repository interface for active liveness session persistence."""

from typing import Awaitable, Callable, Optional, Protocol, TypeVar

from app.api.schemas.active_liveness import ActiveLivenessSession

T = TypeVar("T")


class IActiveLivenessSessionRepository(Protocol):
    """Protocol for active liveness session persistence implementations."""

    async def save(self, session: ActiveLivenessSession) -> None:
        """Save or replace a session."""

    async def get(self, session_id: str) -> Optional[ActiveLivenessSession]:
        """Get a session by ID."""

    async def delete(self, session_id: str) -> bool:
        """Delete a session by ID."""

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists."""

    async def mutate(
        self,
        session_id: str,
        handler: Callable[[ActiveLivenessSession], T | Awaitable[T]],
    ) -> Optional[T]:
        """Atomically mutate a session and return a handler result."""

    async def close(self) -> None:
        """Release repository resources."""
