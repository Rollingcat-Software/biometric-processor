"""In-memory cosine matcher for encrypted biometric embeddings (Phase 1.3b).

Once pgvector plaintext columns are dropped (migration 0007), similarity
search can no longer delegate to PostgreSQL's ``<=>`` operator. This
service replaces it with a brute-force cosine match over an in-memory,
per-tenant, LRU+TTL-cached matrix that is built by decrypting the
tenant's active centroid ciphertexts.

Design notes
------------
* **Brute force is fine at the expected scale.** Tenants in production
  rarely hold more than O(10^5) enrollments each; a 512-dim float32 matrix
  at 100k rows is ~200 MiB and a matrix-vector multiply on modern CPUs
  runs in tens of milliseconds. Above O(10^6) per tenant we will need to
  rethink (e.g. FAISS on decrypted data held in a memory-locked pool).
* **Cache eviction is dual: LRU + TTL.** LRU bounds memory use across a
  fleet of tenants; TTL bounds how stale a cached matrix can be
  (defaults to 60 seconds, matching the requirement).
* **Cache invalidation on writes.** Enrollment and delete paths call
  :meth:`invalidate` so the next match rebuilds the matrix from
  authoritative ciphertext.
* **Per-tenant rebuild lock.** Two concurrent cache-miss coroutines for
  the same tenant must not both hammer the DB; an :class:`asyncio.Lock`
  per tenant serializes rebuilds.

The repository contract expected by :class:`EmbeddingMatchService`
(``repo.load_active_ciphertexts``) is deliberately thin so both the face
and voice repositories can be adapted without entangling this class in
their SQL.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple
from uuid import UUID

import numpy as np

from app.security.embedding_cipher import EmbeddingCipher
from app.security.tenant_dek_store import TenantDekStore

logger = logging.getLogger(__name__)


class EncryptedEmbeddingRepository(Protocol):
    """Thin contract implemented by face and voice pgvector repositories."""

    async def load_active_ciphertexts(
        self, tenant_id: UUID
    ) -> List[Tuple[str, str]]:
        """Return ``[(user_id, ciphertext), ...]`` for the tenant's active
        centroid rows. Order is not significant.
        """
        ...


@dataclass
class _TenantMatrixEntry:
    """Cached per-tenant matrix plus its user-id alignment."""

    matrix: np.ndarray  # shape (N, D), rows already L2-normalized
    user_ids: List[str]  # len(user_ids) == N, aligned with matrix rows
    built_at: float


class EmbeddingMatchService:
    """Per-tenant encrypted cosine matcher.

    Parameters
    ----------
    repo:
        Object satisfying :class:`EncryptedEmbeddingRepository`.
    cipher:
        Shared :class:`EmbeddingCipher` (used to decrypt ciphertexts).
    dek_store:
        :class:`TenantDekStore` for retrieving the tenant DEK — only used
        by higher-level matchers that envelope-encrypt with a per-tenant
        DEK. The current implementation uses the KEK directly for
        correctness; ``dek_store`` is retained on the service so a future
        two-tier implementation does not change the public API.
    modality:
        ``"face"`` or ``"voice"``; mixed into the AAD so a face ciphertext
        cannot be decrypted as a voice ciphertext.
    cache_ttl_sec:
        Seconds a built matrix may live before rebuild.
    max_tenants:
        LRU upper bound on the number of cached matrices.
    """

    def __init__(
        self,
        repo: EncryptedEmbeddingRepository,
        cipher: EmbeddingCipher,
        dek_store: Optional[TenantDekStore] = None,
        modality: str = "face",
        cache_ttl_sec: int = 60,
        max_tenants: int = 64,
    ) -> None:
        if modality not in ("face", "voice"):
            raise ValueError("modality must be 'face' or 'voice'")
        self._repo = repo
        self._cipher = cipher
        self._dek_store = dek_store
        self._modality = modality
        self._cache_ttl_sec = int(cache_ttl_sec)
        self._max_tenants = int(max_tenants)

        self._cache: "OrderedDict[UUID, _TenantMatrixEntry]" = OrderedDict()
        self._cache_lock = asyncio.Lock()
        self._tenant_locks: dict[UUID, asyncio.Lock] = {}
        self._tenant_locks_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def search_top_k(
        self,
        tenant_id: UUID,
        query_vec: np.ndarray,
        k: int,
        threshold: float,
    ) -> List[Tuple[str, float]]:
        """Return up to ``k`` ``(user_id, distance)`` pairs sorted ascending.

        ``distance`` is ``1 - cosine_similarity``, bounded in ``[0, 2]``.
        Results with distance greater than ``threshold`` are filtered out.
        An empty list is a valid return (no matches, or empty tenant).
        """
        if not isinstance(tenant_id, UUID):
            raise ValueError("tenant_id must be a uuid.UUID")
        if not isinstance(query_vec, np.ndarray):
            raise ValueError("query_vec must be a numpy.ndarray")
        if query_vec.ndim != 1:
            raise ValueError("query_vec must be 1-D")
        if k <= 0:
            return []

        entry = await self._get_or_build_matrix(tenant_id, dim_hint=query_vec.shape[0])
        if entry.matrix.shape[0] == 0:
            return []

        # L2-normalize the query (matrix rows are already normalized).
        q = query_vec.astype(np.float32, copy=False)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0.0:
            return []
        q_unit = q / q_norm

        # similarity in [-1, 1]; distance = 1 - similarity in [0, 2].
        sims = entry.matrix @ q_unit
        dists = 1.0 - sims

        # Argpartition for top-k then a small sort; cheaper than a full sort
        # when N >> k.
        n = dists.shape[0]
        top_k = min(k, n)
        if top_k == n:
            idx = np.argsort(dists, kind="stable")
        else:
            part = np.argpartition(dists, top_k - 1)[:top_k]
            idx = part[np.argsort(dists[part], kind="stable")]

        results: List[Tuple[str, float]] = []
        for i in idx:
            d = float(dists[i])
            if d > threshold:
                continue
            results.append((entry.user_ids[i], d))
        return results

    async def invalidate(self, tenant_id: UUID) -> None:
        """Drop the cached matrix for ``tenant_id``. Call after enroll /
        delete so the next match rebuilds from authoritative data.
        """
        async with self._cache_lock:
            self._cache.pop(tenant_id, None)

    async def invalidate_all(self) -> None:
        """Flush the entire cache (used on KEK rotation)."""
        async with self._cache_lock:
            self._cache.clear()

    # ------------------------------------------------------------------
    # Internal: matrix build / cache
    # ------------------------------------------------------------------
    async def _get_or_build_matrix(
        self, tenant_id: UUID, dim_hint: int
    ) -> _TenantMatrixEntry:
        entry = await self._cache_peek(tenant_id)
        if entry is not None:
            return entry

        lock = await self._tenant_lock(tenant_id)
        async with lock:
            # Re-check under the lock.
            entry = await self._cache_peek(tenant_id)
            if entry is not None:
                return entry

            entry = await self._build_matrix(tenant_id, dim_hint)
            await self._cache_put(tenant_id, entry)
            return entry

    async def _build_matrix(
        self, tenant_id: UUID, dim_hint: int
    ) -> _TenantMatrixEntry:
        rows = await self._repo.load_active_ciphertexts(tenant_id)
        user_ids: List[str] = []
        vectors: List[np.ndarray] = []

        for user_id, ciphertext in rows:
            aad = self._aad_for(tenant_id, user_id)
            try:
                raw = self._cipher.decrypt(ciphertext, aad)
            except ValueError:
                logger.warning(
                    "match.build.decrypt_failed modality=%s tenant_id=%s "
                    "user_id=%s — skipping row",
                    self._modality,
                    tenant_id,
                    user_id,
                )
                continue
            vec = np.frombuffer(raw, dtype=np.float32)
            if vec.size == 0 or (dim_hint and vec.size != dim_hint):
                logger.warning(
                    "match.build.dim_mismatch modality=%s tenant_id=%s "
                    "user_id=%s size=%d expected=%d — skipping row",
                    self._modality,
                    tenant_id,
                    user_id,
                    vec.size,
                    dim_hint,
                )
                continue
            norm = float(np.linalg.norm(vec))
            if norm == 0.0:
                continue
            vectors.append(vec / norm)
            user_ids.append(user_id)

        if not vectors:
            matrix = np.zeros((0, dim_hint or 0), dtype=np.float32)
        else:
            matrix = np.stack(vectors, axis=0).astype(np.float32, copy=False)

        return _TenantMatrixEntry(
            matrix=matrix, user_ids=user_ids, built_at=time.monotonic()
        )

    async def _cache_peek(self, tenant_id: UUID) -> Optional[_TenantMatrixEntry]:
        async with self._cache_lock:
            entry = self._cache.get(tenant_id)
            if entry is None:
                return None
            if time.monotonic() - entry.built_at > self._cache_ttl_sec:
                self._cache.pop(tenant_id, None)
                return None
            self._cache.move_to_end(tenant_id)
            return entry

    async def _cache_put(self, tenant_id: UUID, entry: _TenantMatrixEntry) -> None:
        async with self._cache_lock:
            self._cache[tenant_id] = entry
            self._cache.move_to_end(tenant_id)
            while len(self._cache) > self._max_tenants:
                self._cache.popitem(last=False)

    async def _tenant_lock(self, tenant_id: UUID) -> asyncio.Lock:
        async with self._tenant_locks_lock:
            lock = self._tenant_locks.get(tenant_id)
            if lock is None:
                lock = asyncio.Lock()
                self._tenant_locks[tenant_id] = lock
        return lock

    def _aad_for(self, tenant_id: UUID, user_id: str) -> bytes:
        """Build AAD ``<modality>:<tenant_uuid_bytes>:<user_id_bytes>``."""
        return (
            self._modality.encode("ascii")
            + b":"
            + tenant_id.bytes
            + b":"
            + user_id.encode("utf-8")
        )
