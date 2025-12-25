"""Idempotency store for preventing duplicate operations.

This module implements idempotency key storage and validation to prevent
duplicate enrollment requests caused by client retries, network issues,
or user error.

Following:
- Single Responsibility: Only handles idempotency logic
- Dependency Inversion: Uses abstract cache interface
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class IdempotentResponse:
    """Stored response for idempotency checking.

    Attributes:
        request_hash: Hash of request parameters
        response_data: Original response data
        status_code: HTTP status code
        created_at: When response was stored
        user_id: User ID from request (for logging)
    """
    request_hash: str
    response_data: dict[str, Any]
    status_code: int
    created_at: datetime
    user_id: str


class IdempotencyStore:
    """In-memory idempotency store with TTL.

    Prevents duplicate operations by storing request results keyed by
    idempotency_key. If the same key is used again within the TTL window,
    the cached response is returned instead of re-executing the operation.

    Thread Safety:
        Uses asyncio.Lock to protect concurrent access to the store.

    Usage:
        store = IdempotencyStore(ttl_hours=24)

        # Before executing operation:
        cached = await store.get_response(idempotency_key, request_hash)
        if cached:
            return cached.response_data

        # After operation completes:
        await store.store_response(
            idempotency_key, request_hash, response_data, status_code, user_id
        )

    Attributes:
        _store: In-memory cache of idempotent responses
        _lock: Async lock for thread safety
        _ttl_seconds: Time-to-live for cached responses
    """

    def __init__(self, ttl_hours: int = 24) -> None:
        """Initialize idempotency store.

        Args:
            ttl_hours: Time-to-live for stored responses in hours (default: 24)
        """
        self._store: dict[str, IdempotentResponse] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_hours * 3600

        logger.info(f"IdempotencyStore initialized with {ttl_hours}h TTL")

    @staticmethod
    def hash_request(user_id: str, tenant_id: Optional[str], file_hash: str) -> str:
        """Create hash of request parameters.

        This hash ensures that only identical requests (same user, tenant, and file)
        can reuse the idempotency key. Different requests with the same key will be
        detected and rejected.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier
            file_hash: Hash of uploaded file content

        Returns:
            SHA-256 hash of request parameters
        """
        # Include all parameters that make a request unique
        params = f"{user_id}|{tenant_id or 'none'}|{file_hash}"
        return hashlib.sha256(params.encode()).hexdigest()

    @staticmethod
    def hash_file_content(content: bytes) -> str:
        """Create hash of file content.

        Args:
            content: File content bytes

        Returns:
            SHA-256 hash of file content
        """
        return hashlib.sha256(content).hexdigest()

    async def get_response(
        self,
        idempotency_key: str,
        request_hash: str
    ) -> Optional[IdempotentResponse]:
        """Get cached response for idempotency key.

        Args:
            idempotency_key: Client-provided idempotency key
            request_hash: Hash of request parameters

        Returns:
            Cached response if found and not expired, None otherwise

        Raises:
            ValueError: If idempotency key exists but request parameters differ
        """
        async with self._lock:
            # Check if key exists
            if idempotency_key not in self._store:
                logger.debug(f"Idempotency key not found: {idempotency_key}")
                return None

            cached = self._store[idempotency_key]

            # Check if expired
            age_seconds = (datetime.utcnow() - cached.created_at).total_seconds()
            if age_seconds > self._ttl_seconds:
                logger.info(
                    f"Idempotency key expired (age: {age_seconds:.0f}s): {idempotency_key}"
                )
                del self._store[idempotency_key]
                return None

            # Check if request parameters match
            if cached.request_hash != request_hash:
                logger.warning(
                    f"Idempotency key conflict: same key, different request parameters "
                    f"(key: {idempotency_key}, user: {cached.user_id})"
                )
                raise ValueError(
                    f"Idempotency key '{idempotency_key}' already used for a different request. "
                    f"Please use a unique idempotency key for each distinct enrollment."
                )

            logger.info(
                f"Idempotency cache hit: {idempotency_key} "
                f"(age: {age_seconds:.0f}s, user: {cached.user_id})"
            )
            return cached

    async def store_response(
        self,
        idempotency_key: str,
        request_hash: str,
        response_data: dict[str, Any],
        status_code: int,
        user_id: str
    ) -> None:
        """Store response for future idempotency checks.

        Args:
            idempotency_key: Client-provided idempotency key
            request_hash: Hash of request parameters
            response_data: Response data to cache
            status_code: HTTP status code
            user_id: User ID from request
        """
        async with self._lock:
            # Clean up expired entries periodically (simple heuristic)
            if len(self._store) % 100 == 0:
                await self._cleanup_expired()

            response = IdempotentResponse(
                request_hash=request_hash,
                response_data=response_data,
                status_code=status_code,
                created_at=datetime.utcnow(),
                user_id=user_id
            )

            self._store[idempotency_key] = response

            logger.info(
                f"Stored idempotent response: {idempotency_key} "
                f"(user: {user_id}, status: {status_code})"
            )

    async def _cleanup_expired(self) -> None:
        """Remove expired entries from store.

        This method should be called while holding the lock.
        """
        now = datetime.utcnow()
        expired_keys = [
            key for key, response in self._store.items()
            if (now - response.created_at).total_seconds() > self._ttl_seconds
        ]

        for key in expired_keys:
            del self._store[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired idempotency keys")

    async def get_stats(self) -> dict[str, Any]:
        """Get idempotency store statistics.

        Returns:
            Statistics dictionary
        """
        async with self._lock:
            total_entries = len(self._store)

            if total_entries == 0:
                return {
                    "total_entries": 0,
                    "oldest_entry_age_seconds": 0,
                    "newest_entry_age_seconds": 0,
                    "ttl_seconds": self._ttl_seconds
                }

            now = datetime.utcnow()
            ages = [
                (now - response.created_at).total_seconds()
                for response in self._store.values()
            ]

            return {
                "total_entries": total_entries,
                "oldest_entry_age_seconds": max(ages),
                "newest_entry_age_seconds": min(ages),
                "ttl_seconds": self._ttl_seconds
            }
