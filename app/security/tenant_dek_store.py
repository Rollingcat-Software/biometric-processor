"""Per-tenant Data Encryption Key (DEK) store.

Design (Phase 1.3b):
    * Each tenant has a dedicated 256-bit DEK.
    * DEKs are wrapped with the shared KEK via :class:`EmbeddingCipher` and
      stored in the ``tenant_deks`` table (migration 0005).
    * AAD when wrapping the DEK is ``b"tenant-dek:" + tenant_id.bytes`` so
      that a DEK row swapped between tenants will fail to unwrap.
    * Unwrapped DEKs are cached in-process (LRU, TTL) to avoid a database
      round-trip on every match.

This module is intentionally agnostic to the database driver. Callers
supply a ``db_conn_factory`` that must return an async context manager
yielding an :class:`asyncpg.Connection`-like object with ``fetchrow`` and
``execute`` coroutines. Tests inject a fake connection factory.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict
from typing import Awaitable, Callable, Optional
from uuid import UUID

from app.security.embedding_cipher import EmbeddingCipher

logger = logging.getLogger(__name__)


# ``async with db_conn_factory() as conn:`` must yield something asyncpg-like.
DbConnFactory = Callable[[], "AsyncConnCtx"]


class AsyncConnCtx:  # pragma: no cover - typing helper
    """Protocol-ish stand-in for asyncpg's acquired-connection context."""

    async def __aenter__(self) -> "AsyncConnCtx": ...
    async def __aexit__(self, *exc_info) -> None: ...
    async def fetchrow(self, query: str, *args): ...
    async def execute(self, query: str, *args): ...


class TenantDekStore:
    """Wrap, unwrap, and cache tenant DEKs.

    Parameters
    ----------
    cipher:
        Shared :class:`EmbeddingCipher`. The cipher's KEK wraps the DEK.
    db_conn_factory:
        Zero-arg callable returning an async context manager. On
        ``__aenter__`` it must yield an object exposing asyncpg-style
        ``fetchrow`` and ``execute`` coroutines.
    cache_max_size:
        Max number of unwrapped DEKs retained in-process (LRU eviction).
    cache_ttl_sec:
        Time-to-live for cached DEKs, in seconds.
    dek_generator:
        Optional override for DEK generation; defaults to
        ``lambda: os.urandom(32)``. Tests use this to inject deterministic
        keys.
    """

    _DEK_BYTES = 32
    _AAD_PREFIX = b"tenant-dek:"

    def __init__(
        self,
        cipher: EmbeddingCipher,
        db_conn_factory: DbConnFactory,
        cache_max_size: int = 256,
        cache_ttl_sec: int = 600,
        dek_generator: Optional[Callable[[], bytes]] = None,
    ) -> None:
        self._cipher = cipher
        self._db_conn_factory = db_conn_factory
        self._cache_max_size = int(cache_max_size)
        self._cache_ttl_sec = int(cache_ttl_sec)
        self._dek_generator = dek_generator or (lambda: os.urandom(self._DEK_BYTES))

        # OrderedDict as LRU: key = tenant_id (UUID), value = (dek_bytes, inserted_at).
        self._cache: "OrderedDict[UUID, tuple[bytes, float]]" = OrderedDict()
        self._cache_lock = asyncio.Lock()
        # Per-tenant locks to serialize the "load or create" race.
        self._tenant_locks: dict[UUID, asyncio.Lock] = {}
        self._tenant_locks_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_or_create(self, tenant_id: UUID) -> bytes:
        """Return the unwrapped 32-byte DEK for ``tenant_id``.

        On cache miss the row is read from ``tenant_deks``. If absent, a
        new DEK is generated, wrapped with the KEK, and inserted. Returns
        the unwrapped DEK either way.
        """
        if not isinstance(tenant_id, UUID):
            raise ValueError("tenant_id must be a uuid.UUID")

        cached = await self._cache_get(tenant_id)
        if cached is not None:
            return cached

        lock = await self._tenant_lock(tenant_id)
        async with lock:
            # Re-check cache after acquiring the per-tenant lock.
            cached = await self._cache_get(tenant_id)
            if cached is not None:
                return cached

            dek = await self._load_or_create(tenant_id)
            await self._cache_put(tenant_id, dek)
            return dek

    async def invalidate(self, tenant_id: UUID) -> None:
        """Drop the cached DEK for ``tenant_id`` (used on KEK rotation)."""
        async with self._cache_lock:
            self._cache.pop(tenant_id, None)

    # ------------------------------------------------------------------
    # DB interaction
    # ------------------------------------------------------------------
    async def _load_or_create(self, tenant_id: UUID) -> bytes:
        aad = self._aad_for(tenant_id)

        async with self._db_conn_factory() as conn:
            row = await conn.fetchrow(
                "SELECT wrapped_dek FROM tenant_deks WHERE tenant_id = $1",
                tenant_id,
            )

            if row is not None and row["wrapped_dek"] is not None:
                wrapped = row["wrapped_dek"]
                if isinstance(wrapped, (bytes, bytearray, memoryview)):
                    wrapped_str = bytes(wrapped).decode("ascii")
                else:
                    wrapped_str = str(wrapped)
                try:
                    dek = self._cipher.decrypt(wrapped_str, aad)
                except ValueError:
                    # DEK unwrap failed — do NOT fall through to create. A
                    # failed unwrap on an existing row indicates KEK rotation
                    # or tampering; operators must intervene.
                    logger.error(
                        "tenant_dek.unwrap.failed tenant_id=%s (possible KEK "
                        "rotation or AAD mismatch)",
                        tenant_id,
                    )
                    raise
                if len(dek) != self._DEK_BYTES:
                    raise ValueError(
                        "Malformed tenant DEK (expected 32 bytes after unwrap)"
                    )
                return dek

            # Create a fresh DEK and insert atomically (ON CONFLICT DO NOTHING
            # in case another worker raced us).
            new_dek = self._dek_generator()
            if len(new_dek) != self._DEK_BYTES:
                raise ValueError("DEK generator must produce 32 bytes")

            wrapped = self._cipher.encrypt(new_dek, aad)
            # Also store a random IV column for schema parity with the
            # embedding tables; the wrapper already embeds its IV in the
            # ciphertext so this column is informational.
            iv = os.urandom(12)

            await conn.execute(
                """
                INSERT INTO tenant_deks (tenant_id, wrapped_dek, iv)
                VALUES ($1, $2, $3)
                ON CONFLICT (tenant_id) DO NOTHING
                """,
                tenant_id,
                wrapped.encode("ascii"),
                iv,
            )

            # Re-read so concurrent writers resolve to the same DEK.
            row = await conn.fetchrow(
                "SELECT wrapped_dek FROM tenant_deks WHERE tenant_id = $1",
                tenant_id,
            )
            if row is None or row["wrapped_dek"] is None:
                raise RuntimeError(
                    f"Failed to persist tenant DEK for tenant_id={tenant_id}"
                )
            wrapped_value = row["wrapped_dek"]
            if isinstance(wrapped_value, (bytes, bytearray, memoryview)):
                wrapped_str = bytes(wrapped_value).decode("ascii")
            else:
                wrapped_str = str(wrapped_value)
            return self._cipher.decrypt(wrapped_str, aad)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    async def _cache_get(self, tenant_id: UUID) -> Optional[bytes]:
        async with self._cache_lock:
            entry = self._cache.get(tenant_id)
            if entry is None:
                return None
            dek, inserted_at = entry
            if time.monotonic() - inserted_at > self._cache_ttl_sec:
                self._cache.pop(tenant_id, None)
                return None
            # Move to MRU.
            self._cache.move_to_end(tenant_id)
            return dek

    async def _cache_put(self, tenant_id: UUID, dek: bytes) -> None:
        async with self._cache_lock:
            self._cache[tenant_id] = (dek, time.monotonic())
            self._cache.move_to_end(tenant_id)
            while len(self._cache) > self._cache_max_size:
                self._cache.popitem(last=False)

    async def _tenant_lock(self, tenant_id: UUID) -> asyncio.Lock:
        async with self._tenant_locks_lock:
            lock = self._tenant_locks.get(tenant_id)
            if lock is None:
                lock = asyncio.Lock()
                self._tenant_locks[tenant_id] = lock
        return lock

    @classmethod
    def _aad_for(cls, tenant_id: UUID) -> bytes:
        return cls._AAD_PREFIX + tenant_id.bytes
