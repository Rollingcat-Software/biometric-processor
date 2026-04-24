"""Parity check: encrypted match returns identical top-1 user and distance
(within 1e-6) to the plaintext cosine calculation on the same data.

This test is DB-free. It uses a fake repository that holds ciphertexts
in memory so the parity of :class:`EmbeddingMatchService` with a naive
reference implementation can be verified without PostgreSQL or asyncpg.
"""

from __future__ import annotations

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


def _aad(modality: str, tenant: UUID, user_id: str) -> bytes:
    return (
        modality.encode("ascii")
        + b":"
        + tenant.bytes
        + b":"
        + user_id.encode("utf-8")
    )


class _FakeRepo:
    def __init__(self) -> None:
        self._by_tenant: dict[UUID, List[Tuple[str, str]]] = {}

    def seed(self, tenant: UUID, rows: List[Tuple[str, str]]) -> None:
        self._by_tenant[tenant] = list(rows)

    async def load_active_ciphertexts(self, tenant_id: UUID):
        return list(self._by_tenant.get(tenant_id, []))


def _reference_cosine_top_k(
    matrix: np.ndarray, user_ids: list[str], query: np.ndarray, k: int, threshold: float
) -> list[tuple[str, float]]:
    """Brute-force cosine top-k against plaintext — used as the source of
    truth for the parity assertion.
    """
    mat_norm = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    q_norm = query / np.linalg.norm(query)
    sims = mat_norm @ q_norm
    dists = 1.0 - sims
    order = np.argsort(dists)
    out = []
    for i in order[:k]:
        d = float(dists[i])
        if d > threshold:
            continue
        out.append((user_ids[i], d))
    return out


@pytest.mark.asyncio
@pytest.mark.integration
async def test_encrypted_parity_matches_plaintext_top1() -> None:
    tenant = uuid4()
    rng = np.random.default_rng(seed=1234)
    dim = 64
    n = 100

    # 100 random embeddings (float32).
    raw = rng.standard_normal((n, dim)).astype(np.float32)
    user_ids = [f"user_{i:03d}" for i in range(n)]

    cipher = EmbeddingCipher(_fresh_kek_b64())
    repo = _FakeRepo()
    ciphertexts = [
        (
            uid,
            cipher.encrypt(raw[i].tobytes(), _aad("face", tenant, uid)),
        )
        for i, uid in enumerate(user_ids)
    ]
    repo.seed(tenant, ciphertexts)

    svc = EmbeddingMatchService(
        repo=repo, cipher=cipher, modality="face",
        cache_ttl_sec=60, max_tenants=4,
    )

    # 25 different queries — each is a small perturbation of one of the
    # enrolled vectors so top-1 is unambiguous.
    for target in range(0, n, 4):
        query = raw[target] + rng.standard_normal(dim).astype(np.float32) * 1e-3

        reference = _reference_cosine_top_k(raw, user_ids, query, k=1, threshold=2.0)
        actual = await svc.search_top_k(tenant, query, k=1, threshold=2.0)

        assert reference, "reference must have a match"
        assert actual, "encrypted path must have a match"
        assert reference[0][0] == actual[0][0]
        assert reference[0][1] == pytest.approx(actual[0][1], abs=1e-6)
