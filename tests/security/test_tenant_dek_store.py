"""Tests for :class:`app.security.tenant_dek_store.TenantDekStore`.

The store is DB-backed in production; these tests swap in a fake async
connection factory so no PostgreSQL instance is required.
"""

from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest

from app.security.embedding_cipher import EmbeddingCipher
from app.security.tenant_dek_store import TenantDekStore


def _fresh_kek_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


class _FakeConn:
    """Minimal asyncpg.Connection stand-in backed by an in-memory dict."""

    def __init__(self, rows: dict[UUID, dict]) -> None:
        self._rows = rows

    async def fetchrow(self, query: str, *args):
        # Only one SELECT shape is used by the store.
        tenant_id = args[0]
        row = self._rows.get(tenant_id)
        return row

    async def execute(self, query: str, *args):
        # Only one INSERT shape is used by the store.
        # INSERT INTO tenant_deks (tenant_id, wrapped_dek, iv) ... ON CONFLICT DO NOTHING
        tenant_id, wrapped_dek, iv = args
        self._rows.setdefault(
            tenant_id,
            {"tenant_id": tenant_id, "wrapped_dek": wrapped_dek, "iv": iv},
        )


def _factory(rows: dict[UUID, dict]):
    @asynccontextmanager
    async def _cm():
        yield _FakeConn(rows)
    return _cm


@pytest.mark.asyncio
async def test_wrap_unwrap_round_trip() -> None:
    kek = _fresh_kek_b64()
    cipher = EmbeddingCipher(kek)
    rows: dict[UUID, dict] = {}
    store = TenantDekStore(cipher, _factory(rows))

    tenant = uuid4()
    dek1 = await store.get_or_create(tenant)
    assert len(dek1) == 32
    assert tenant in rows

    # Second call returns the cached value.
    dek2 = await store.get_or_create(tenant)
    assert dek1 == dek2

    # Invalidate the cache — we must still return the same unwrapped DEK
    # from the persisted wrapped row.
    await store.invalidate(tenant)
    dek3 = await store.get_or_create(tenant)
    assert dek1 == dek3


@pytest.mark.asyncio
async def test_cross_tenant_dek_swap_rejects() -> None:
    """A wrapped DEK from tenant A must not unwrap as tenant B."""
    kek = _fresh_kek_b64()
    cipher = EmbeddingCipher(kek)
    rows: dict[UUID, dict] = {}
    store = TenantDekStore(cipher, _factory(rows))

    tenant_a = uuid4()
    tenant_b = uuid4()

    # Create DEK for tenant A.
    await store.get_or_create(tenant_a)
    assert tenant_a in rows

    # Swap: put A's wrapped row under tenant B's key.
    rows[tenant_b] = {"wrapped_dek": rows[tenant_a]["wrapped_dek"], "iv": rows[tenant_a]["iv"]}

    # Fresh store (no cache). Request tenant B — must fail to unwrap
    # because AAD = "tenant-dek:" || tenant_b.bytes.
    store2 = TenantDekStore(cipher, _factory(rows))
    with pytest.raises(ValueError):
        await store2.get_or_create(tenant_b)


@pytest.mark.asyncio
async def test_rejects_non_uuid_tenant_id() -> None:
    cipher = EmbeddingCipher(_fresh_kek_b64())
    store = TenantDekStore(cipher, _factory({}))

    with pytest.raises(ValueError):
        await store.get_or_create("not-a-uuid")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_different_tenants_get_different_deks() -> None:
    cipher = EmbeddingCipher(_fresh_kek_b64())
    store = TenantDekStore(cipher, _factory({}))

    dek_a = await store.get_or_create(uuid4())
    dek_b = await store.get_or_create(uuid4())
    assert dek_a != dek_b
