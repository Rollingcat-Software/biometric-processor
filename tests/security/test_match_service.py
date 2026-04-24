"""Tests for :class:`app.security.embedding_match.EmbeddingMatchService`."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import List, Tuple
from uuid import UUID, uuid4

import numpy as np
import pytest

from app.security.embedding_cipher import EmbeddingCipher
from app.security.embedding_match import EmbeddingMatchService


def _fresh_kek_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


def _aad(modality: str, tenant_id: UUID, user_id: str) -> bytes:
    return (
        modality.encode("ascii")
        + b":"
        + tenant_id.bytes
        + b":"
        + user_id.encode("utf-8")
    )


class _FakeRepo:
    """Repository double that returns pre-encrypted ciphertexts."""

    def __init__(self) -> None:
        self._by_tenant: dict[UUID, List[Tuple[str, str]]] = {}
        self.load_calls = 0

    def seed(self, tenant: UUID, rows: List[Tuple[str, str]]) -> None:
        self._by_tenant[tenant] = list(rows)

    async def load_active_ciphertexts(self, tenant_id: UUID):
        self.load_calls += 1
        return list(self._by_tenant.get(tenant_id, []))


def _build_service(ttl: int = 60, max_tenants: int = 8):
    cipher = EmbeddingCipher(_fresh_kek_b64())
    repo = _FakeRepo()
    svc = EmbeddingMatchService(
        repo=repo,
        cipher=cipher,
        modality="face",
        cache_ttl_sec=ttl,
        max_tenants=max_tenants,
    )
    return svc, repo, cipher


def _encrypt_vec(cipher: EmbeddingCipher, modality: str, tenant: UUID,
                 user_id: str, vec: np.ndarray) -> str:
    return cipher.encrypt(vec.astype(np.float32).tobytes(), _aad(modality, tenant, user_id))


@pytest.mark.asyncio
async def test_search_returns_top1_for_exact_match() -> None:
    svc, repo, cipher = _build_service()
    tenant = uuid4()

    # Three known users, 8-dim embeddings for clarity.
    rng = np.random.default_rng(seed=0)
    known = {f"user_{i}": rng.standard_normal(8).astype(np.float32) for i in range(3)}
    rows = [
        (uid, _encrypt_vec(cipher, "face", tenant, uid, v))
        for uid, v in known.items()
    ]
    repo.seed(tenant, rows)

    # Query is exactly one of the known vectors — top-1 must be that user,
    # distance near 0.
    target_user = "user_1"
    results = await svc.search_top_k(tenant, known[target_user], k=3, threshold=0.5)
    assert results, "expected at least one match"
    top_user, top_distance = results[0]
    assert top_user == target_user
    assert top_distance == pytest.approx(0.0, abs=1e-5)


@pytest.mark.asyncio
async def test_threshold_filters_results() -> None:
    svc, repo, cipher = _build_service()
    tenant = uuid4()

    # Two orthogonal vectors — similarity = 0, distance = 1.
    v1 = np.array([1, 0, 0, 0], dtype=np.float32)
    v2 = np.array([0, 1, 0, 0], dtype=np.float32)
    repo.seed(
        tenant,
        [
            ("u1", _encrypt_vec(cipher, "face", tenant, "u1", v1)),
            ("u2", _encrypt_vec(cipher, "face", tenant, "u2", v2)),
        ],
    )

    # Tight threshold — only the exact match should pass.
    results = await svc.search_top_k(tenant, v1, k=5, threshold=0.1)
    assert [r[0] for r in results] == ["u1"]

    # Loose threshold — both pass.
    results = await svc.search_top_k(tenant, v1, k=5, threshold=1.5)
    assert sorted(r[0] for r in results) == ["u1", "u2"]


@pytest.mark.asyncio
async def test_cache_hit_avoids_rebuild() -> None:
    svc, repo, cipher = _build_service()
    tenant = uuid4()
    v = np.array([1, 2, 3, 4], dtype=np.float32)
    repo.seed(tenant, [("u", _encrypt_vec(cipher, "face", tenant, "u", v))])

    await svc.search_top_k(tenant, v, k=1, threshold=1.0)
    await svc.search_top_k(tenant, v, k=1, threshold=1.0)

    assert repo.load_calls == 1, "second search must hit the cache"


@pytest.mark.asyncio
async def test_ttl_expiry_triggers_rebuild() -> None:
    svc, repo, cipher = _build_service(ttl=1)
    tenant = uuid4()
    v = np.array([1, 2, 3, 4], dtype=np.float32)
    repo.seed(tenant, [("u", _encrypt_vec(cipher, "face", tenant, "u", v))])

    await svc.search_top_k(tenant, v, k=1, threshold=1.0)

    # Simulate TTL expiry by poking built_at backward.
    async with svc._cache_lock:  # type: ignore[attr-defined]
        entry = list(svc._cache.values())[0]  # type: ignore[attr-defined]
        entry.built_at -= 10

    await svc.search_top_k(tenant, v, k=1, threshold=1.0)
    assert repo.load_calls == 2


@pytest.mark.asyncio
async def test_invalidate_drops_cache() -> None:
    svc, repo, cipher = _build_service()
    tenant = uuid4()
    v = np.array([1, 2, 3, 4], dtype=np.float32)
    repo.seed(tenant, [("u", _encrypt_vec(cipher, "face", tenant, "u", v))])

    await svc.search_top_k(tenant, v, k=1, threshold=1.0)
    await svc.invalidate(tenant)
    await svc.search_top_k(tenant, v, k=1, threshold=1.0)
    assert repo.load_calls == 2


@pytest.mark.asyncio
async def test_per_tenant_isolation_via_aad() -> None:
    """A ciphertext seeded under a different tenant must be skipped (the
    AAD mismatches when the matcher rebuilds for the wrong tenant).
    """
    svc, repo, cipher = _build_service()
    tenant_a = uuid4()
    tenant_b = uuid4()

    v = np.array([1, 0, 0], dtype=np.float32)
    # Build a ciphertext correctly bound to tenant_a.
    ct = _encrypt_vec(cipher, "face", tenant_a, "u", v)
    # Seed it under tenant_b's bucket — the matcher will try to decrypt with
    # AAD bound to tenant_b and reject it.
    repo.seed(tenant_b, [("u", ct)])

    results = await svc.search_top_k(tenant_b, v, k=1, threshold=2.0)
    assert results == [], "cross-tenant ciphertexts must be filtered"


@pytest.mark.asyncio
async def test_zero_query_returns_empty() -> None:
    svc, repo, cipher = _build_service()
    tenant = uuid4()
    v = np.array([1, 2, 3, 4], dtype=np.float32)
    repo.seed(tenant, [("u", _encrypt_vec(cipher, "face", tenant, "u", v))])

    zero = np.zeros(4, dtype=np.float32)
    assert await svc.search_top_k(tenant, zero, k=1, threshold=2.0) == []


@pytest.mark.asyncio
async def test_lru_eviction_respects_max_tenants() -> None:
    svc, repo, cipher = _build_service(max_tenants=2)

    def seed(tid: UUID) -> np.ndarray:
        v = np.array([1, 2, 3, 4], dtype=np.float32)
        repo.seed(tid, [("u", _encrypt_vec(cipher, "face", tid, "u", v))])
        return v

    t1, t2, t3 = uuid4(), uuid4(), uuid4()
    v1 = seed(t1)
    v2 = seed(t2)
    v3 = seed(t3)

    await svc.search_top_k(t1, v1, k=1, threshold=1.0)
    await svc.search_top_k(t2, v2, k=1, threshold=1.0)
    await svc.search_top_k(t3, v3, k=1, threshold=1.0)

    # t1 should have been evicted — another search must rebuild.
    before = repo.load_calls
    await svc.search_top_k(t1, v1, k=1, threshold=1.0)
    assert repo.load_calls == before + 1
