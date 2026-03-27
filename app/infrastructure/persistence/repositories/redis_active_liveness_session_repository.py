"""Redis-backed repository for active liveness sessions."""

import inspect
import logging
import time
from typing import Awaitable, Callable, Optional, TypeVar

import redis.asyncio as redis

from app.api.schemas.active_liveness import ActiveLivenessSession
from app.domain.interfaces.active_liveness_session_repository import (
    IActiveLivenessSessionRepository,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RedisActiveLivenessSessionRepository(IActiveLivenessSessionRepository):
    """Redis-backed active liveness session store with optimistic locking."""

    KEY_PREFIX = "active_liveness:session:"
    MIN_TTL_SECONDS = 1
    COMPLETED_SESSION_TTL_SECONDS = 300

    def __init__(
        self,
        redis_url: str,
        max_connections: int = 10,
        key_prefix: str = KEY_PREFIX,
    ) -> None:
        self._redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=max_connections,
        )
        self._key_prefix = key_prefix
        logger.info("Creating active liveness session repository (redis)")

    def _key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"

    def _is_expired(
        self,
        session: ActiveLivenessSession,
        now: Optional[float] = None,
    ) -> bool:
        if session.is_complete:
            return False
        return (now or time.time()) >= session.expires_at

    def _calculate_ttl(
        self,
        session: ActiveLivenessSession,
        now: Optional[float] = None,
    ) -> int:
        if session.is_complete:
            return self.COMPLETED_SESSION_TTL_SECONDS

        remaining = int(session.expires_at - (now or time.time()))
        return max(remaining, self.MIN_TTL_SECONDS)

    async def save(self, session: ActiveLivenessSession) -> None:
        await self._redis.setex(
            self._key(session.session_id),
            self._calculate_ttl(session),
            session.model_dump_json(),
        )

    async def get(self, session_id: str) -> Optional[ActiveLivenessSession]:
        payload = await self._redis.get(self._key(session_id))
        if payload is None:
            return None

        session = ActiveLivenessSession.model_validate_json(payload)
        if self._is_expired(session):
            await self.delete(session_id)
            return None
        return session.model_copy(deep=True)

    async def delete(self, session_id: str) -> bool:
        deleted = await self._redis.delete(self._key(session_id))
        return deleted > 0

    async def exists(self, session_id: str) -> bool:
        return await self.get(session_id) is not None

    async def mutate(
        self,
        session_id: str,
        handler: Callable[[ActiveLivenessSession], T | Awaitable[T]],
    ) -> Optional[T]:
        key = self._key(session_id)

        async with self._redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    payload = await pipe.get(key)
                    if payload is None:
                        await pipe.unwatch()
                        return None

                    stored_session = ActiveLivenessSession.model_validate_json(payload)
                    if self._is_expired(stored_session):
                        await pipe.unwatch()
                        await self.delete(session_id)
                        return None

                    working_copy = stored_session.model_copy(deep=True)
                    result = handler(working_copy)
                    if inspect.isawaitable(result):
                        result = await result

                    pipe.multi()
                    pipe.setex(
                        key,
                        self._calculate_ttl(working_copy),
                        working_copy.model_dump_json(),
                    )
                    await pipe.execute()
                    return result
                except redis.WatchError:
                    logger.warning(
                        "Concurrent modification of active liveness session %s, retrying",
                        session_id,
                    )
                    continue

    async def close(self) -> None:
        await self._redis.close()
