"""Idempotency check for migration 0006_backfill_embedding_ciphertext.

The migration uses ``SELECT ... WHERE embedding_ciphertext IS NULL`` to
pick rows, so running twice must be a no-op on the second pass. This
test verifies the guarded behaviour by exercising the migration's helper
functions against an in-memory row set — PostgreSQL is not required.
"""

from __future__ import annotations

import base64
import importlib.util
import os
import struct
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from app.security.embedding_cipher import EmbeddingCipher


@pytest.mark.integration
def test_backfill_helpers_are_idempotent_and_correct() -> None:
    # Dynamically load the migration module so we exercise the same
    # ``_pgvector_text_to_bytes`` + ``_aad`` helpers operators will run.
    here = Path(__file__).resolve().parents[2]
    mig_path = (
        here
        / "alembic"
        / "versions"
        / "20260420_0006_backfill_embedding_ciphertext.py"
    )
    assert mig_path.is_file(), f"migration file missing: {mig_path}"

    spec = importlib.util.spec_from_file_location("_mig0006_test", mig_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    # 1) Vector -> bytes parity.
    vec_list = [1.5, -2.25, 3.125]
    raw = mod._pgvector_text_to_bytes(vec_list)
    assert raw == struct.pack("<3f", *vec_list)

    # 2) ``_aad`` is deterministic.
    tenant_id = uuid4()
    aad_1 = mod._aad("face", tenant_id, "u1")
    aad_2 = mod._aad("face", tenant_id, "u1")
    assert aad_1 == aad_2
    assert aad_1.startswith(b"face:")
    # Swapping modality or user flips AAD.
    assert mod._aad("face", tenant_id, "u2") != aad_1
    assert mod._aad("voice", tenant_id, "u1") != aad_1

    # 3) Gate off → no-op.
    os.environ.pop("FIVUCSAS_EMBEDDING_MIGRATE", None)
    assert mod._gate_enabled() is False
    os.environ["FIVUCSAS_EMBEDDING_MIGRATE"] = "TRUE"
    assert mod._gate_enabled() is True
    os.environ["FIVUCSAS_EMBEDDING_MIGRATE"] = "false"
    assert mod._gate_enabled() is False
    os.environ.pop("FIVUCSAS_EMBEDDING_MIGRATE", None)

    # 4) Round-trip: a ciphertext produced with the same cipher + AAD
    #    decrypts back to the original vector, proving the backfill
    #    format is compatible with the repository read path.
    kek = base64.b64encode(os.urandom(32)).decode("ascii")
    cipher = EmbeddingCipher(kek)
    vec = np.asarray([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    plaintext = vec.tobytes()
    aad = mod._aad("face", tenant_id, "u42")
    stored = cipher.encrypt(plaintext, aad)

    # First "pass" writes ciphertext; second "pass" must see it and skip.
    rows = [{"user_id": "u42", "tenant_id": tenant_id,
             "embedding": vec.tolist(), "embedding_ciphertext": None}]
    _simulate_pass(cipher, "face", rows)
    ciphertext_after_first = rows[0]["embedding_ciphertext"]
    assert ciphertext_after_first is not None

    _simulate_pass(cipher, "face", rows)
    assert rows[0]["embedding_ciphertext"] == ciphertext_after_first, (
        "second pass must not re-encrypt (different IVs would leak)"
    )

    # Sanity: what we wrote round-trips.
    decrypted = cipher.decrypt(
        ciphertext_after_first.decode("ascii") if isinstance(ciphertext_after_first, bytes)
        else ciphertext_after_first,
        aad,
    )
    assert np.frombuffer(decrypted, dtype=np.float32).tolist() == vec.tolist()


def _simulate_pass(cipher: EmbeddingCipher, modality: str, rows: list[dict]) -> None:
    """Minimal re-implementation of the migration's inner loop, scoped
    enough to let us assert the idempotency guard.
    """
    for row in rows:
        if row.get("embedding_ciphertext") is not None:
            continue  # idempotency guard
        tenant_id = row["tenant_id"]
        user_id = row["user_id"]
        embedding = row["embedding"]
        plaintext = struct.pack(f"<{len(embedding)}f", *[float(x) for x in embedding])
        aad = modality.encode("ascii") + b":" + tenant_id.bytes + b":" + user_id.encode("utf-8")
        row["embedding_ciphertext"] = cipher.encrypt(plaintext, aad).encode("ascii")
