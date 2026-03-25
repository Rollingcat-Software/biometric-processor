"""In-memory repository for active liveness sessions."""

import asyncio
import inspect
import logging
import time
from typing import Awaitable, Callable, Optional, TypeVar

from app.api.schemas.active_liveness import ActiveLivenessSession
from app.domain.interfaces.active_liveness_session_repository import IActiveLivenessSessionRepository

logger = logging.getLogger(__name__)

T = TypeVar("T")


class InMemoryActiveLivenessSessionRepository(IActiveLivenessSessionRepository):
    """Concurrency-safe in-memory active liveness session store."""

    def __init__(self) -> None:
        self._storage: dict[str, ActiveLivenessSession] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._storage_lock = asyncio.Lock()
        logger.info("Creating active liveness session repository (in-memory)")

    def _is_expired(self, session: ActiveLivenessSession, now: Optional[float] = None) -> bool:
        if session.is_complete:
            return False
        timestamp = now or time.time()
        return timestamp >= session.expires_at

    def _cleanup_expired_unlocked(
        self,
        now: Optional[float] = None,
        exclude_session_ids: Optional[set[str]] = None,
    ) -> None:
        timestamp = now or time.time()
        excluded = exclude_session_ids or set()
        expired_ids = [
            session_id
            for session_id, session in self._storage.items()
            if session_id not in excluded and self._is_expired(session, timestamp)
        ]
        for session_id in expired_ids:
            self._storage.pop(session_id, None)
            self._session_locks.pop(session_id, None)

    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        async with self._storage_lock:
            self._cleanup_expired_unlocked(exclude_session_ids={session_id})
            return self._session_locks.setdefault(session_id, asyncio.Lock())

    async def save(self, session: ActiveLivenessSession) -> None:
        async with self._storage_lock:
            self._cleanup_expired_unlocked()
            self._storage[session.session_id] = session.model_copy(deep=True)
            self._session_locks.setdefault(session.session_id, asyncio.Lock())

    async def get(self, session_id: str) -> Optional[ActiveLivenessSession]:
        async with self._storage_lock:
            self._cleanup_expired_unlocked(exclude_session_ids={session_id})
            session = self._storage.get(session_id)
            return session.model_copy(deep=True) if session else None

    async def delete(self, session_id: str) -> bool:
        session_lock = await self._get_session_lock(session_id)
        async with session_lock:
            async with self._storage_lock:
                self._cleanup_expired_unlocked()
                deleted = self._storage.pop(session_id, None) is not None
                self._session_locks.pop(session_id, None)
                return deleted

    async def exists(self, session_id: str) -> bool:
        return await self.get(session_id) is not None

    async def mutate(
        self,
        session_id: str,
        handler: Callable[[ActiveLivenessSession], T | Awaitable[T]],
    ) -> Optional[T]:
        session_lock = await self._get_session_lock(session_id)

        async with session_lock:
            async with self._storage_lock:
                self._cleanup_expired_unlocked(exclude_session_ids={session_id})
                stored_session = self._storage.get(session_id)
                if stored_session is None:
                    return None
                working_copy = stored_session.model_copy(deep=True)

            result = handler(working_copy)
            if inspect.isawaitable(result):
                result = await result

            async with self._storage_lock:
                self._cleanup_expired_unlocked(exclude_session_ids={session_id})
                if session_id in self._storage:
                    self._storage[session_id] = working_copy

            return result

    async def close(self) -> None:
        async with self._storage_lock:
            self._storage.clear()
            self._session_locks.clear()
