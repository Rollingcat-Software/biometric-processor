"""Route-level tests for POST /api/v1/nfc/verify-authenticity.

Exercises the FastAPI wiring + the base64/JSON contract agent-api consumes,
including the operator CSCA trust-store loading from a configurable directory.
The cryptographic verdicts themselves are covered exhaustively in
``tests/unit/domain/services/test_emrtd_passive_auth.py``; here we prove the
HTTP surface, the trust-store-from-disk path, and the fail-closed default.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.routes.nfc as nfc_route
from app.api.routes.nfc import router as nfc_router

# Reuse the SOD/CSCA/DS fixture builders from the service-level test suite.
from tests.unit.domain.services.test_emrtd_passive_auth import (  # noqa: E402
    _build_lds,
    _build_sod,
    _make_cert,
)
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(nfc_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def sod_bundle():
    """Build a coherent CSCA/DS/SOD set and return the b64 request payload
    plus the CSCA cert PEM so a test can drop it into a trust dir."""
    csca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ds_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csca_cert = _make_cert(
        "Route CSCA", "Route CSCA", csca_key, csca_key.public_key(), True
    )
    ds_cert = _make_cert(
        "Route Document Signer", "Route CSCA", csca_key, ds_key.public_key(), False
    )
    data_groups = {
        1: b"\x61\x10DG1-MRZ-PAYLOAD!",
        2: b"\x75\x20" + b"FAKE_DG2_PORTRAIT_BYTES_32_LONG_",
    }
    lds_der = _build_lds(data_groups)
    sod_der = _build_sod(lds_der, ds_cert, ds_key)

    return {
        "csca_pem": csca_cert.public_bytes(serialization.Encoding.PEM),
        "request": {
            "sod_b64": base64.b64encode(sod_der).decode("ascii"),
            "data_groups": {
                str(n): base64.b64encode(b).decode("ascii")
                for n, b in data_groups.items()
            },
        },
    }


@pytest.fixture(autouse=True)
def _clear_trust_cache():
    """The route memoizes trust-store loads; reset between tests."""
    nfc_route._csca_certs_cached.cache_clear()
    yield
    nfc_route._csca_certs_cached.cache_clear()


def _point_trust_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(nfc_route.settings, "NFC_CSCA_TRUST_DIR", str(tmp_path))


def test_happy_path_authentic(client, sod_bundle, tmp_path, monkeypatch):
    (tmp_path / "csca.pem").write_bytes(sod_bundle["csca_pem"])
    _point_trust_dir(monkeypatch, tmp_path)

    resp = client.post(
        "/api/v1/nfc/verify-authenticity", json=sod_bundle["request"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_authentic"] is True
    assert body["reason_code"] == "OK"
    assert body["csca_matched"] is True
    assert body["dg_hash_results"] == {"1": True, "2": True}
    assert body["sod_hash_algorithm"] == "sha256"
    assert "Document Signer" in body["ds_subject"]


def test_empty_trust_store_fails_closed(client, sod_bundle, tmp_path, monkeypatch):
    # Trust dir exists but holds no certs -> NO_TRUST_STORE, fail-closed.
    _point_trust_dir(monkeypatch, tmp_path)

    resp = client.post(
        "/api/v1/nfc/verify-authenticity", json=sod_bundle["request"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_authentic"] is False
    assert body["reason_code"] == "NO_TRUST_STORE"


def test_tampered_dg_rejected(client, sod_bundle, tmp_path, monkeypatch):
    (tmp_path / "csca.pem").write_bytes(sod_bundle["csca_pem"])
    _point_trust_dir(monkeypatch, tmp_path)

    req = dict(sod_bundle["request"])
    dgs = dict(req["data_groups"])
    # Replace DG2 with different bytes -> hash no longer matches the SOD.
    dgs["2"] = base64.b64encode(b"\x75\x05HELLO").decode("ascii")
    req["data_groups"] = dgs

    resp = client.post("/api/v1/nfc/verify-authenticity", json=req)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_authentic"] is False
    assert body["reason_code"] == "DG_HASH_MISMATCH"
    assert body["dg_hash_results"]["2"] is False


def test_invalid_sod_base64_returns_400(client):
    resp = client.post(
        "/api/v1/nfc/verify-authenticity",
        json={"sod_b64": "***not-base64***", "data_groups": {"1": "AAAA"}},
    )
    assert resp.status_code == 400
    assert "sod_b64" in resp.json()["detail"]


def test_empty_data_groups_returns_400(client, sod_bundle):
    resp = client.post(
        "/api/v1/nfc/verify-authenticity",
        json={"sod_b64": sod_bundle["request"]["sod_b64"], "data_groups": {}},
    )
    assert resp.status_code == 400


def test_non_numeric_dg_key_returns_400(client, sod_bundle):
    resp = client.post(
        "/api/v1/nfc/verify-authenticity",
        json={
            "sod_b64": sod_bundle["request"]["sod_b64"],
            "data_groups": {"face": "AAAA"},
        },
    )
    assert resp.status_code == 400
